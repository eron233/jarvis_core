"""FreeLLMAPI: gateway externo opcional, via proxy HTTP SOMENTE em loopback.

ATENCAO: apesar de a API usar localhost, o servidor FreeLLMAPI pode
transmitir prompts a provedores externos. Este modulo nao e um LLM offline.
"""
from __future__ import annotations

import json
import math
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
from urllib.parse import urlparse


_MAX_REQUEST_BYTES = 512 * 1024
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def validate_freellmapi_endpoint(url: str) -> Optional[str]:
    """Admite somente HTTP loopback e path exato /v1; sem redirects remotos."""
    try:
        url_parts = urlparse(str(url))
        port = url_parts.port
    except (ValueError, TypeError):
        return "Endereco do FreeLLMAPI invalido."
    if url_parts.scheme != "http" or url_parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return "O gateway FreeLLMAPI deve usar HTTP em loopback local."
    if port is not None and not (1 <= port <= 65535):
        return "Porta invalida."
    if (url_parts.path != "/v1" or url_parts.username is not None
        or url_parts.password is not None or url_parts.query or url_parts.fragment):
        return "Endereco deve ser http://127.0.0.1:3001/v1, sem credenciais ou parametros."
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class FreeLLMAPIBackend:
    """Cliente nao persistente, sem proxy de ambiente nem redirects."""

    name = "freellmapi"

    def __init__(self, *, base_url: str, api_key: Optional[str], timeout_seconds: float = 30.0):
        self.base_url = str(base_url).rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = max(1.0, min(120.0, float(timeout_seconds)))
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    @property
    def configured(self) -> bool:
        return validate_freellmapi_endpoint(self.base_url) is None and bool(self.api_key)

    def _request(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        reason = validate_freellmapi_endpoint(self.base_url)
        if reason:
            return {"status": "bloqueado", "motivo": reason}
        if not self.api_key:
            return {"status": "indisponivel", "motivo": "Chave unificada FreeLLMAPI nao configurada."}

        data = None
        if body is not None:
            try:
                data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError, UnicodeError):
                return {"status": "entrada_invalida", "motivo": "Payload nao serializavel."}
            if len(data) > _MAX_REQUEST_BYTES:
                return {"status": "bloqueado", "motivo": "Solicitacao excede o limite de 512 KiB."}
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method="POST" if data is not None else "GET",
        )
        started = time.perf_counter()
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                routed = response.headers.get("X-Routed-Via")
                if len(raw) > _MAX_RESPONSE_BYTES:
                    return {"status": "erro", "motivo": "Resposta excede o limite de 2 MiB."}
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                return {"status": "erro", "motivo": "Resposta do gateway nao e objeto JSON."}
            return {
                "status": "sucesso",
                "dados": parsed,
                "modelo_servido": routed[:180] if isinstance(routed, str) else None,
                "latencia_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        except urllib.error.HTTPError as exc:
            # Nao ecoar corpos de erro, URL, credenciais nem detalhes de provedores.
            return {"status": "indisponivel", "motivo": f"Gateway respondeu HTTP {exc.code}."}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeError):
            return {"status": "indisponivel", "motivo": "Gateway FreeLLMAPI inacessivel ou resposta invalida."}

    def list_models(self) -> Dict[str, Any]:
        result = self._request("/models")
        if result["status"] != "sucesso":
            return {**result, "provider": self.name, "modelos": []}
        data = result["dados"].get("data")
        if not isinstance(data, list):
            return {"status": "erro", "provider": self.name, "modelos": [],
                    "motivo": "Catalogo de modelos invalido."}
        return {"status": "sucesso", "provider": self.name,
                "modelos": [item["id"] for item in data[:1000]
                           if isinstance(item, dict) and isinstance(item.get("id"), str)],
                "latencia_ms": result["latencia_ms"],
                "observacao": "Modelos listados nao sao prova de cota/disponibilidade."}

    def chat(self, *, model: str, messages: List[Dict[str, Any]],
             max_tokens: Optional[int] = None, temperature: Optional[float] = None,
             tools: Optional[List[Dict[str, Any]]] = None,
             tool_choice: Optional[Any] = None,
             response_format: Optional[Dict[str, Any]] = None,
             extra_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if extra_body:
            return {"status": "bloqueado", "provider": self.name, "modelo": model,
                    "motivo": "FreeLLMAPI nao aceita campos extras nao auditados."}
        if not isinstance(model, str) or not model.strip() or not isinstance(messages, list) or not messages:
            return {"status": "entrada_invalida", "provider": self.name}
        if not isinstance(max_tokens or 1024, int) or isinstance(max_tokens, bool):
            return {"status": "entrada_invalida", "provider": self.name}
        limit = max_tokens if max_tokens is not None else 1024
        if not 1 <= limit <= 4096:
            return {"status": "bloqueado", "provider": self.name,
                    "motivo": "Limite max_tokens externo deve estar entre 1 e 4096."}
        if temperature is None:
            temp = 0.2
        elif isinstance(temperature, (int, float)) and not isinstance(temperature, bool) and math.isfinite(temperature):
            temp = float(temperature)
        else:
            return {"status": "entrada_invalida", "provider": self.name}
        if not 0 <= temp <= 2:
            return {"status": "entrada_invalida", "provider": self.name}
        payload: Dict[str, Any] = {
            "model": model, "messages": messages, "stream": False,
            "max_tokens": limit, "temperature": temp,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if response_format is not None:
            payload["response_format"] = response_format
        result = self._request("/chat/completions", payload)
        if result["status"] != "sucesso":
            return {**result, "provider": self.name, "modelo": model}
        data = result["dados"]
        choices = data.get("choices")
        if not (isinstance(choices, list) and choices and isinstance(choices[0], dict)
                and isinstance(choices[0].get("message"), dict)):
            return {"status": "erro", "provider": self.name, "modelo": model,
                    "motivo": "Resposta sem choice/message valido."}
        message = choices[0]["message"]
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        completion = usage.get("completion_tokens")
        latency = result["latencia_ms"]
        return {
            "status": "sucesso",
            "provider": self.name,
            "modelo": data.get("model") if isinstance(data.get("model"), str) else model,
            "modelo_servido": result["modelo_servido"],
            "conteudo": message.get("content"),
            "tool_calls": message.get("tool_calls") or [],
            "finish_reason": choices[0].get("finish_reason"),
            "usage": usage,
            "latencia_ms": latency,
            "tokens_por_segundo_estimado": (
                round(completion / (latency / 1000), 3)
                if isinstance(completion, (int, float)) and latency > 0 else None
            ),
            "id_resposta": data.get("id"),
            "created": data.get("created"),
            "processamento_externo_possivel": True,
            "custo_confirmado_zero": False,
        }
