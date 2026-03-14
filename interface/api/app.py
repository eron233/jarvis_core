"""API minima de controle do JARVIS."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from main import SystemLoopConfig, bootstrap_runtime
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.system_config import (
    DEFAULT_API_TOKEN,
    DEFAULT_TRUSTED_DEVICE_ID,
    JarvisEnvironmentConfig,
)

TOKEN_HEADER = "X-Jarvis-Token"
DEVICE_HEADER = "X-Jarvis-Device-Id"
SESSION_COOKIE = "jarvis_trusted_device"
SAFE_WORKER_IDS = {"runtime", "finance", "study", "studio"}
DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "index.html"
ACCESS_GATE_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "access_gate.html"


class TaskCreateRequest(BaseModel):
    """Payload minimo para adicionar uma tarefa na fila via API."""

    task_id: str
    goal: str
    description: str = ""
    domain: str = "runtime"
    worker: Optional[str] = None
    urgency: int = 0
    impact: int = 0
    cost: int = 0
    reversibility: int = 0
    risk: int = 0
    approved: bool = True
    requires_supervision: bool = False
    evidence: list[str] = Field(default_factory=list)
    parent_goal_id: Optional[str] = None


def create_app(
    runtime: InternalAgentRuntime | None = None,
    api_token: str | None = None,
    trusted_device_id: str | None = None,
    config: SystemLoopConfig | None = None,
    deployment_config: JarvisEnvironmentConfig | None = None,
) -> FastAPI:
    """Cria uma aplicacao FastAPI ligada ao runtime atual."""

    effective_deployment_config = deployment_config or JarvisEnvironmentConfig.from_env()

    if effective_deployment_config is not None and config is None:
        config = SystemLoopConfig(
            cycle_sleep_seconds=effective_deployment_config.loop_interval_seconds,
            idle_sleep_seconds=effective_deployment_config.idle_sleep_seconds,
            install_signal_handlers=False,
            queue_storage_path=effective_deployment_config.queue_storage_path,
            semantic_storage_path=effective_deployment_config.semantic_storage_path,
            procedural_storage_path=effective_deployment_config.procedural_storage_path,
            goal_storage_path=effective_deployment_config.goals_storage_path,
        )

    app = FastAPI(
        title="API do JARVIS",
        version="0.1.0",
        description="Camada minima de acesso ao nucleo operacional do JARVIS.",
    )
    app.state.runtime = runtime or InternalAgentRuntime()
    app.state.system_config = config or SystemLoopConfig()
    app.state.deployment_config = effective_deployment_config
    app.state.bootstrap_state = (
        app.state.runtime.describe_state() if app.state.runtime.status == "initialized" else None
    )
    app.state.started_at = datetime.now(timezone.utc).isoformat()
    app.state.last_cycle_result = getattr(app.state.runtime, "last_cycle_result", None)
    app.state.api_token = (
        api_token
        or getattr(effective_deployment_config, "token", None)
        or DEFAULT_API_TOKEN
    )
    app.state.trusted_device_id = (
        trusted_device_id
        or getattr(effective_deployment_config, "trusted_device_id", None)
        or DEFAULT_TRUSTED_DEVICE_ID
    )
    app.state.enable_dashboard = (
        True if effective_deployment_config is None else effective_deployment_config.enable_dashboard
    )
    app.state.environment_report = _build_environment_report(app)

    def require_trusted_device(
        request: Request,
        x_jarvis_token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
        x_jarvis_device_id: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    ) -> Dict[str, str]:
        return _validate_trusted_access(
            request=request,
            token=x_jarvis_token,
            device_id=x_jarvis_device_id,
        )

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/painel", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @app.get("/painel", include_in_schema=False, response_class=HTMLResponse)
    def get_dashboard(request: Request) -> HTMLResponse:
        if not request.app.state.enable_dashboard:
            return HTMLResponse(
                "<html><body><h1>Painel desabilitado neste ambiente.</h1></body></html>",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if _has_valid_dashboard_session(request):
            return HTMLResponse(DASHBOARD_PATH.read_text(encoding="utf-8"))
        return HTMLResponse(ACCESS_GATE_PATH.read_text(encoding="utf-8"))

    @app.post("/api/auth/device-session")
    def create_device_session(
        request: Request,
        x_jarvis_token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
        x_jarvis_device_id: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    ) -> JSONResponse:
        access_context = _validate_trusted_access(
            request=request,
            token=x_jarvis_token,
            device_id=x_jarvis_device_id,
        )
        response = JSONResponse(
            {
                "mensagem": "Dispositivo confiavel validado com sucesso.",
                "device_id": access_context["device_id"],
            }
        )
        response.set_cookie(
            key=SESSION_COOKIE,
            value=_build_trusted_session_value(request.app.state.api_token, access_context["device_id"]),
            httponly=True,
            samesite="lax",
        )
        return response

    @app.delete("/api/auth/device-session")
    def clear_device_session() -> JSONResponse:
        response = JSONResponse({"mensagem": "Sessao do dispositivo removida."})
        response.delete_cookie(SESSION_COOKIE)
        return response

    @app.get("/api/saude")
    def healthcheck(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        estado = runtime.describe_state()
        return {
            "mensagem": "API do JARVIS ativa.",
            "status": "ok" if estado["status"] == "initialized" else "degradado",
            "status_ptbr": "saudavel" if estado["status"] == "initialized" else "degradado",
            "api_iniciada_em": app.state.started_at,
        }

    @app.get("/health")
    def deploy_healthcheck(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        payload = runtime.build_health_report(
            api_started_at=app.state.started_at,
            token_configurado=_is_runtime_secret_configured(app.state.api_token, DEFAULT_API_TOKEN),
            dispositivo_confiavel_configurado=_is_runtime_secret_configured(
                app.state.trusted_device_id,
                DEFAULT_TRUSTED_DEVICE_ID,
            ),
        )
        payload["mensagem"] = "Healthcheck de deploy do JARVIS."
        payload["ambiente"] = _build_environment_report(request.app)
        return payload

    @app.get("/api/health", dependencies=[Depends(require_trusted_device)])
    def detailed_healthcheck(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        payload = runtime.build_health_report(
            api_started_at=app.state.started_at,
            token_configurado=_is_runtime_secret_configured(app.state.api_token, DEFAULT_API_TOKEN),
            dispositivo_confiavel_configurado=_is_runtime_secret_configured(
                app.state.trusted_device_id,
                DEFAULT_TRUSTED_DEVICE_ID,
            ),
        )
        payload["ambiente"] = _build_environment_report(request.app)
        return payload

    @app.get("/api/status", dependencies=[Depends(require_trusted_device)])
    def get_status(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return {
            "mensagem": "Estado atual do sistema recuperado com sucesso.",
            "dados": runtime.describe_state(),
        }

    @app.post("/api/ciclos/executar", dependencies=[Depends(require_trusted_device)])
    def run_cycle(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        cycle_result = runtime.run_planner_cycle()
        app.state.last_cycle_result = cycle_result
        return {
            "mensagem": "Ciclo do planejador executado.",
            "resultado": cycle_result,
        }

    @app.get("/api/tarefas", dependencies=[Depends(require_trusted_device)])
    def list_tasks(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        tasks = runtime.list_tasks()
        return {
            "mensagem": "Fila atual consultada com sucesso.",
            "total": len(tasks),
            "tarefas": tasks,
        }

    @app.post("/api/tarefas", dependencies=[Depends(require_trusted_device)])
    def add_task(payload: TaskCreateRequest, request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        task = payload.model_dump()
        task["worker"] = _resolve_worker(task.get("worker"), task["domain"])
        task["approval"] = {
            "approved": task.pop("approved"),
            "requires_supervision": task.pop("requires_supervision"),
        }
        enqueued_task = runtime.enqueue_task(task)
        return {
            "mensagem": "Tarefa adicionada a fila com sucesso.",
            "tarefa": enqueued_task,
        }

    @app.get("/api/objetivos", dependencies=[Depends(require_trusted_device)])
    def get_goals(request: Request, goal_id: str | None = Query(default=None)) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return {
            "mensagem": "Relatorio de objetivos recuperado.",
            "dados": runtime.get_goal_report(goal_id),
        }

    @app.get("/api/memoria/recente", dependencies=[Depends(require_trusted_device)])
    def get_recent_memory(
        request: Request,
        limit: int = Query(default=5, ge=1, le=20),
        domain: str | None = Query(default=None),
    ) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        semantic_entries = runtime.get_recent_semantic_entries(limit=limit, domain=domain)
        recent_events = runtime.get_recent_events(limit=limit)
        return {
            "mensagem": "Memoria recente recuperada.",
            "entradas_semanticas": semantic_entries,
            "eventos_episodicos": recent_events,
        }

    @app.get("/api/relatorio", dependencies=[Depends(require_trusted_device)])
    def get_report(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        report = runtime.build_system_report(last_cycle_result=app.state.last_cycle_result)
        report["ambiente"] = _build_environment_report(request.app)
        return report

    @app.get("/api/relatorio/sistema", dependencies=[Depends(require_trusted_device)])
    def get_system_report(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        report = runtime.build_system_report(last_cycle_result=app.state.last_cycle_result)
        report["ambiente"] = _build_environment_report(request.app)
        return report

    @app.get("/api/relatorio/fila", dependencies=[Depends(require_trusted_device)])
    def get_queue_report(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return runtime.build_queue_report()

    @app.get("/api/relatorio/objetivos", dependencies=[Depends(require_trusted_device)])
    def get_goals_report(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return runtime.build_goal_operational_report()

    @app.get("/api/relatorio/memoria", dependencies=[Depends(require_trusted_device)])
    def get_memory_report(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return runtime.build_memory_report()

    @app.get("/api/relatorio/auditoria", dependencies=[Depends(require_trusted_device)])
    def get_audit_report(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return runtime.build_audit_report()

    return app


def _resolve_worker(requested_worker: str | None, domain: str) -> str:
    if requested_worker:
        return requested_worker
    if domain in SAFE_WORKER_IDS:
        return f"worker_{domain}"
    return "worker_runtime"


def _ensure_runtime_initialized(request: Request) -> InternalAgentRuntime:
    if request.app.state.bootstrap_state is not None:
        return request.app.state.runtime

    runtime, bootstrap_state = bootstrap_runtime(
        runtime=request.app.state.runtime,
        config=request.app.state.system_config,
    )
    request.app.state.runtime = runtime
    request.app.state.bootstrap_state = bootstrap_state
    request.app.state.environment_report = _build_environment_report(request.app)
    return runtime


def _validate_trusted_access(
    request: Request,
    token: str | None,
    device_id: str | None,
) -> Dict[str, str]:
    runtime = _ensure_runtime_initialized(request)
    client_host = request.client.host if request.client is not None else None

    if not token:
        _record_access_attempt(runtime, request, device_id, False, "missing_token", client_host)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso ausente.",
        )

    if token != request.app.state.api_token:
        _record_access_attempt(runtime, request, device_id, False, "invalid_token", client_host)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso invalido.",
        )

    if not device_id:
        _record_access_attempt(runtime, request, device_id, False, "missing_device_id", client_host)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identificador do dispositivo ausente.",
        )

    if device_id != request.app.state.trusted_device_id:
        _record_access_attempt(runtime, request, device_id, False, "untrusted_device", client_host)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dispositivo nao autorizado.",
        )

    _record_access_attempt(runtime, request, device_id, True, None, client_host)
    return {"device_id": device_id}


def _record_access_attempt(
    runtime: InternalAgentRuntime,
    request: Request,
    device_id: str | None,
    allowed: bool,
    reason: str | None,
    client_host: str | None,
) -> None:
    runtime.record_access_attempt(
        endpoint=request.url.path,
        method=request.method,
        device_id=device_id,
        allowed=allowed,
        reason=reason,
        client_host=client_host,
    )


def _has_valid_dashboard_session(request: Request) -> bool:
    session_value = request.cookies.get(SESSION_COOKIE)
    if not session_value:
        return False

    expected_value = _build_trusted_session_value(
        request.app.state.api_token,
        request.app.state.trusted_device_id,
    )
    return session_value == expected_value


def _build_trusted_session_value(api_token: str, device_id: str) -> str:
    return hashlib.sha256(f"{api_token}:{device_id}".encode("utf-8")).hexdigest()


def _is_runtime_secret_configured(value: str | None, default_value: str) -> bool:
    return bool(value) and value != default_value


def _build_environment_report(app: FastAPI) -> Dict[str, Any]:
    deployment_config = getattr(app.state, "deployment_config", None)
    if deployment_config is not None:
        return deployment_config.build_environment_report()

    return {
        "ambiente": "local",
        "host_api": "0.0.0.0",
        "porta_api": 8000,
        "loop_runtime_ativo": False,
        "painel_ativo": bool(getattr(app.state, "enable_dashboard", True)),
        "nivel_log": "INFO",
        "paths_persistentes": {
            "queue_storage_path": str(getattr(app.state.system_config, "queue_storage_path", "")),
            "semantic_storage_path": str(getattr(app.state.system_config, "semantic_storage_path", "")),
            "goals_storage_path": str(getattr(app.state.system_config, "goal_storage_path", "")),
        },
        "autenticacao_configurada": {
            "token_configurado": _is_runtime_secret_configured(app.state.api_token, DEFAULT_API_TOKEN),
            "dispositivo_confiavel_configurado": _is_runtime_secret_configured(
                app.state.trusted_device_id,
                DEFAULT_TRUSTED_DEVICE_ID,
            ),
        },
    }


app = create_app()
