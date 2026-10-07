"""
JARVIS - Stack de Inferencia Local

Objetivos:
- abstrair runtimes locais OpenAI-compatible (llama.cpp, Ollama e futuros gateways)
- nao escolher nem inventar um modelo-base
- rotear por tier/capacidade configurada
- medir latencia/uso real
- falhar de forma explicita quando servidor/modelo nao estiver provisionado

A identidade do JARVIS permanece fora do modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import os
import socket
import time
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlparse
import urllib.error
import urllib.request


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _csv(value: Optional[str], default: str = "") -> List[str]:
    raw = value if value is not None else default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class InferenceStackConfig:
    enabled: bool = False
    provider_order: tuple[str, ...] = ("llamacpp", "ollama")

    llamacpp_base_url: str = "http://127.0.0.1:8080/v1"
    llamacpp_api_key: Optional[str] = None

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_api_key: Optional[str] = None

    allow_remote_endpoints: bool = False
    timeout_seconds: float = 120.0
    max_tokens_default: int = 1024
    temperature_default: float = 0.2

    model_light: Optional[str] = None
    model_heavy: Optional[str] = None
    model_coding: Optional[str] = None
    model_reasoning: Optional[str] = None
    model_general: Optional[str] = None

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
    ) -> "InferenceStackConfig":
        env = dict(environ or os.environ)
        order = tuple(_csv(env.get("JARVIS_INFERENCE_PROVIDER_ORDER"), "llamacpp,ollama"))
        return cls(
            enabled=_env_bool(env.get("JARVIS_INFERENCE_ENABLED"), False),
            provider_order=order or ("llamacpp", "ollama"),
            llamacpp_base_url=(env.get("JARVIS_LLAMACPP_BASE_URL") or "http://127.0.0.1:8080/v1").rstrip("/"),
            llamacpp_api_key=(env.get("JARVIS_LLAMACPP_API_KEY") or "").strip() or None,
            ollama_base_url=(env.get("JARVIS_OLLAMA_BASE_URL") or "http://127.0.0.1:11434/v1").rstrip("/"),
            ollama_api_key=(env.get("JARVIS_OLLAMA_API_KEY") or "").strip() or None,
            allow_remote_endpoints=_env_bool(env.get("JARVIS_INFERENCE_ALLOW_REMOTE_ENDPOINTS"), False),
            timeout_seconds=max(1.0, float(env.get("JARVIS_INFERENCE_TIMEOUT_SECONDS", "120"))),
            max_tokens_default=max(1, int(env.get("JARVIS_INFERENCE_MAX_TOKENS", "1024"))),
            temperature_default=max(0.0, min(2.0, float(env.get("JARVIS_INFERENCE_TEMPERATURE", "0.2")))),
            model_light=(env.get("JARVIS_MODEL_LIGHT") or "").strip() or None,
            model_heavy=(env.get("JARVIS_MODEL_HEAVY") or "").strip() or None,
            model_coding=(env.get("JARVIS_MODEL_CODING") or "").strip() or None,
            model_reasoning=(env.get("JARVIS_MODEL_REASONING") or "").strip() or None,
            model_general=(env.get("JARVIS_MODEL_GENERAL") or "").strip() or None,
        )


def validate_inference_endpoint(url: str, allow_remote: bool = False) -> Optional[str]:
    """Restringe endpoints a localhost/loopback por padrao."""

    try:
        parsed = urlparse(str(url).strip())
    except ValueError:
        return "Endpoint invalido."

    if parsed.scheme not in {"http", "https"}:
        return "Endpoint de inferencia deve usar HTTP/HTTPS."
    if not parsed.hostname:
        return "Endpoint sem host."
    if parsed.username is not None or parsed.password is not None:
        return "Credenciais embutidas na URL nao sao permitidas."

    host = parsed.hostname.strip("[]").lower()
    if allow_remote:
        return None
    if host in {"localhost", "localhost.localdomain"}:
        return None

    try:
        ip = ipaddress.ip_address(host)
        return None if ip.is_loopback else "Inferencia remota bloqueada por padrao."
    except ValueError:
        pass

    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            if info and info[4]
        }
    except socket.gaierror:
        return "Host de inferencia nao resolve localmente."

    if not addresses:
        return "Host de inferencia sem endereco resolvido."
    try:
        if all(ipaddress.ip_address(addr).is_loopback for addr in addresses):
            return None
    except ValueError:
        pass
    return "Inferencia remota bloqueada por padrao."


class OpenAICompatibleLocalBackend:
    """Cliente minimo para servidores locais OpenAI-compatible."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: Optional[str],
        config: InferenceStackConfig,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.config = config

    @property
    def configured(self) -> bool:
        return validate_inference_endpoint(
            self.base_url,
            allow_remote=self.config.allow_remote_endpoints,
        ) is None

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def list_models(self) -> Dict[str, Any]:
        reason = validate_inference_endpoint(
            self.base_url,
            allow_remote=self.config.allow_remote_endpoints,
        )
        if reason:
            return {
                "status": "bloqueado",
                "provider": self.name,
                "modelos": [],
                "motivo": reason,
            }

        request = urllib.request.Request(
            f"{self.base_url}/models",
            headers=self._headers(),
            method="GET",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=min(self.config.timeout_seconds, 10.0)) as response:
                payload = json.loads(response.read().decode("utf-8"))
            models = []
            for item in payload.get("data") or []:
                if isinstance(item, dict) and item.get("id"):
                    models.append(str(item["id"]))
            return {
                "status": "sucesso",
                "provider": self.name,
                "modelos": models,
                "latencia_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        except Exception as exc:
            return {
                "status": "indisponivel",
                "provider": self.name,
                "modelos": [],
                "motivo": f"{exc.__class__.__name__}: {exc}",
                "latencia_ms": round((time.perf_counter() - started) * 1000, 3),
            }

    def chat(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        response_format: Optional[Dict[str, Any]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        reason = validate_inference_endpoint(
            self.base_url,
            allow_remote=self.config.allow_remote_endpoints,
        )
        if reason:
            return {
                "status": "bloqueado",
                "provider": self.name,
                "modelo": model,
                "motivo": reason,
            }

        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "max_tokens": int(max_tokens or self.config.max_tokens_default),
            "temperature": (
                self.config.temperature_default
                if temperature is None
                else max(0.0, min(2.0, float(temperature)))
            ),
        }
        if tools:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if response_format is not None:
            body["response_format"] = response_format
        if extra_body:
            body.update(extra_body)

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {
                "status": "indisponivel",
                "provider": self.name,
                "modelo": model,
                "motivo": f"{exc.__class__.__name__}: {exc}",
                "latencia_ms": round((time.perf_counter() - started) * 1000, 3),
            }

        choices = payload.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            return {
                "status": "erro",
                "provider": self.name,
                "modelo": model,
                "motivo": "Resposta OpenAI-compatible sem choices validos.",
                "payload_bruto": payload,
                "latencia_ms": round((time.perf_counter() - started) * 1000, 3),
            }

        message = choices[0].get("message") or {}
        usage = payload.get("usage") or {}
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        completion_tokens = usage.get("completion_tokens")
        tokens_per_second = None
        if isinstance(completion_tokens, (int, float)) and latency_ms > 0:
            tokens_per_second = round(float(completion_tokens) / (latency_ms / 1000.0), 3)

        return {
            "status": "sucesso",
            "provider": self.name,
            "modelo": payload.get("model") or model,
            "conteudo": message.get("content"),
            "tool_calls": message.get("tool_calls") or [],
            "finish_reason": choices[0].get("finish_reason"),
            "usage": usage,
            "latencia_ms": latency_ms,
            "tokens_por_segundo_estimado": tokens_per_second,
            "id_resposta": payload.get("id"),
            "created": payload.get("created"),
        }


class LocalInferenceRouter:
    """Roteia requisicoes para runtimes locais sem escolher o modelo por conta propria."""

    def __init__(self, config: Optional[InferenceStackConfig] = None) -> None:
        self.config = config or InferenceStackConfig.from_env()
        self.backends: Dict[str, OpenAICompatibleLocalBackend] = {
            "llamacpp": OpenAICompatibleLocalBackend(
                name="llamacpp",
                base_url=self.config.llamacpp_base_url,
                api_key=self.config.llamacpp_api_key,
                config=self.config,
            ),
            "ollama": OpenAICompatibleLocalBackend(
                name="ollama",
                base_url=self.config.ollama_base_url,
                api_key=self.config.ollama_api_key,
                config=self.config,
            ),
        }

    def resolve_model(
        self,
        *,
        tier: str = "general",
        capability: Optional[str] = None,
        explicit_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        if explicit_model:
            return {
                "status": "sucesso",
                "modelo": explicit_model,
                "origem": "explicit",
            }

        aliases = {
            "light": self.config.model_light,
            "heavy": self.config.model_heavy,
            "general": self.config.model_general,
            "coding": self.config.model_coding,
            "reasoning": self.config.model_reasoning,
        }
        candidates = []
        if capability:
            candidates.append(str(capability).strip().lower())
        if tier:
            candidates.append(str(tier).strip().lower())
        candidates.append("general")

        seen = set()
        for alias in candidates:
            if alias in seen:
                continue
            seen.add(alias)
            model = aliases.get(alias)
            if model:
                return {
                    "status": "sucesso",
                    "modelo": model,
                    "origem": f"alias:{alias}",
                }

        return {
            "status": "indisponivel",
            "modelo": None,
            "origem": None,
            "motivo": (
                "Nenhum modelo foi escolhido para este tier/capacidade. "
                "A selecao do modelo-base permanece adiada ate o benchmark local."
            ),
        }

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        tier: str = "general",
        capability: Optional[str] = None,
        explicit_model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        response_format: Optional[Dict[str, Any]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.config.enabled:
            return {
                "status": "indisponivel",
                "motivo": "Inferencia local esta desativada.",
                "modelo": None,
            }
        if not messages:
            return {
                "status": "erro",
                "motivo": "messages nao pode ser vazio.",
                "modelo": None,
            }

        resolved = self.resolve_model(
            tier=tier,
            capability=capability,
            explicit_model=explicit_model,
        )
        if resolved["status"] != "sucesso":
            return resolved
        model = str(resolved["modelo"])

        providers = [provider] if provider else list(self.config.provider_order)
        attempts = []
        for name in providers:
            backend = self.backends.get(str(name))
            if backend is None:
                attempts.append({
                    "provider": name,
                    "status": "indisponivel",
                    "motivo": "Provider desconhecido.",
                })
                continue
            result = backend.chat(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice,
                response_format=response_format,
                extra_body=extra_body,
            )
            attempts.append({
                "provider": name,
                "status": result.get("status"),
                "motivo": result.get("motivo"),
            })
            if result.get("status") == "sucesso":
                result["roteamento"] = {
                    "tier": tier,
                    "capability": capability,
                    "model_resolution": resolved,
                    "attempts": attempts,
                }
                return result

        return {
            "status": "indisponivel",
            "modelo": model,
            "motivo": "Nenhum runtime local concluiu a inferencia.",
            "roteamento": {
                "tier": tier,
                "capability": capability,
                "model_resolution": resolved,
                "attempts": attempts,
            },
        }

    def status(self, probe: bool = False) -> Dict[str, Any]:
        providers: Dict[str, Any] = {}
        for name, backend in self.backends.items():
            item: Dict[str, Any] = {
                "base_url": backend.base_url,
                "endpoint_permitido": backend.configured,
            }
            if probe and backend.configured:
                item["probe"] = backend.list_models()
            providers[name] = item

        aliases = {
            "light": self.config.model_light,
            "heavy": self.config.model_heavy,
            "general": self.config.model_general,
            "coding": self.config.model_coding,
            "reasoning": self.config.model_reasoning,
        }
        return {
            "enabled": self.config.enabled,
            "provider_order": list(self.config.provider_order),
            "providers": providers,
            "model_aliases": aliases,
            "modelo_base_escolhido": any(bool(value) for value in aliases.values()),
            "allow_remote_endpoints": self.config.allow_remote_endpoints,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
