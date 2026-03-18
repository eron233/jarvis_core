"""Cliente HTTP leve do app nativo reutilizando a API local do JARVIS."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
from urllib import error, parse, request

from interface.native_app.config import NativeAppConfig
from interface.native_client.jarvis_client import build_authenticated_headers


class ApiClientError(RuntimeError):
    """Erro amigavel de comunicacao com a API local."""


class JarvisApiClient:
    """Encapsula os endpoints reais usados pela interface nativa."""

    def __init__(self, config: NativeAppConfig) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        self.config = config

    def public_healthcheck(self) -> dict[str, Any]:
        """Consulta o healthcheck publico do runtime."""

        return self._request_json(self.config.health_path, authenticated=False)

    def get_detailed_health(self) -> dict[str, Any]:
        """Recupera o healthcheck autenticado rico."""

        return self._request_json("/api/health")

    def get_status(self) -> dict[str, Any]:
        """Retorna o resumo autenticado do runtime."""

        return self._request_json("/api/status")

    def get_runtime_identity(self) -> dict[str, Any]:
        """Retorna a identidade verificavel do runtime ativo."""

        return self._request_json("/api/runtime/identidade")

    def get_goals_report(self) -> dict[str, Any]:
        """Retorna os objetivos ativos e estrategicos."""

        return self._request_json("/api/relatorio/objetivos")

    def get_queue_report(self) -> dict[str, Any]:
        """Retorna o relatorio real da fila."""

        return self._request_json("/api/relatorio/fila")

    def get_memory_report(self) -> dict[str, Any]:
        """Retorna o relatorio real das memorias."""

        return self._request_json("/api/relatorio/memoria")

    def get_audit_report(self) -> dict[str, Any]:
        """Retorna o relatorio real de auditoria."""

        return self._request_json("/api/relatorio/auditoria")

    def get_system_report(self) -> dict[str, Any]:
        """Retorna o relatorio operacional consolidado."""

        return self._request_json("/api/relatorio/sistema")

    def get_cognitive_evolution(self, level: str = "semanal") -> dict[str, Any]:
        """Recupera o payload do mapa cognitivo atual."""

        return self._request_json(f"/api/cognicao/evolucao?nivel={parse.quote(level)}")

    def get_cognitive_analysis(self, level: str = "semanal") -> dict[str, Any]:
        """Recupera a analise textual da evolucao cognitiva."""

        return self._request_json(f"/api/cognicao/evolucao/analise?nivel={parse.quote(level)}")

    def send_command(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        password: str | None = None,
        response_mode: str = "conversacional",
    ) -> dict[str, Any]:
        """Envia um comando real ao endpoint oficial do Jarvis."""

        payload = {
            "texto": str(text or "").strip(),
            "voz_identificada": voice_id or None,
            "senha": password or None,
            "modo_resposta": response_mode,
        }
        return self._request_json("/api/comando", method="POST", payload=payload)

    def fetch_dashboard_bundle(self) -> dict[str, Any]:
        """Agrupa os relatarios usados pela lateral e pelo rodape do app."""

        return {
            "health": self.get_detailed_health(),
            "status": self.get_status(),
            "runtime_identity": self.get_runtime_identity(),
            "system_report": self.get_system_report(),
            "goals_report": self.get_goals_report(),
            "queue_report": self.get_queue_report(),
            "memory_report": self.get_memory_report(),
            "audit_report": self.get_audit_report(),
        }

    def fetch_brain_bundle(self, level: str = "semanal") -> dict[str, Any]:
        """Agrupa o payload visual e a analise cognitiva."""

        return {
            "level": level,
            "evolution": self.get_cognitive_evolution(level=level),
            "analysis": self.get_cognitive_analysis(level=level),
        }

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """Executa uma request JSON contra a API local."""

        url = parse.urljoin(f"{self.config.api_base_url}/", path.lstrip("/"))
        headers = {"Content-Type": "application/json"}
        body: bytes | None = None

        if authenticated:
            headers.update(
                build_authenticated_headers(
                    token=self.config.api_token,
                    device_id=self.config.device_id,
                )
            )

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        http_request = request.Request(
            url=url,
            data=body,
            headers=headers,
            method=method.upper(),
        )

        try:
            with request.urlopen(http_request, timeout=self.config.request_timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            try:
                parsed_detail = json.loads(detail)
                message = parsed_detail.get("detail") or parsed_detail.get("mensagem") or detail
            except json.JSONDecodeError:
                message = detail or str(exc)
            raise ApiClientError(f"Falha HTTP {exc.code}: {message}") from exc
        except error.URLError as exc:
            raise ApiClientError(f"Falha ao conectar na API local: {exc.reason}") from exc

        try:
            parsed = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError as exc:
            raise ApiClientError("A API retornou um JSON invalido para o app nativo.") from exc
        return deepcopy(parsed)

