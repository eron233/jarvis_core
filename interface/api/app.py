"""API minima de controle do JARVIS."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from main import SystemLoopConfig, bootstrap_runtime
from runtime.internal_agent_runtime import InternalAgentRuntime

TOKEN_HEADER = "X-Jarvis-Token"
DEFAULT_API_TOKEN = "jarvis-local-dev-token"
SAFE_WORKER_IDS = {"runtime", "finance", "study", "studio"}
DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "index.html"


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
    config: SystemLoopConfig | None = None,
) -> FastAPI:
    """Cria uma aplicacao FastAPI ligada ao runtime atual."""

    app = FastAPI(
        title="API do JARVIS",
        version="0.1.0",
        description="Camada minima de acesso ao nucleo operacional do JARVIS.",
    )
    app.state.runtime = runtime or InternalAgentRuntime()
    app.state.system_config = config or SystemLoopConfig()
    app.state.bootstrap_state = None
    app.state.started_at = datetime.now(timezone.utc).isoformat()
    app.state.last_cycle_result = None
    app.state.api_token = api_token or os.getenv("JARVIS_API_TOKEN") or DEFAULT_API_TOKEN

    def require_token(
        request: Request,
        x_jarvis_token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
    ) -> None:
        if x_jarvis_token == request.app.state.api_token:
            return

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso invalido ou ausente.",
        )

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/painel", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @app.get("/painel", include_in_schema=False, response_class=HTMLResponse)
    def get_dashboard() -> HTMLResponse:
        return HTMLResponse(DASHBOARD_PATH.read_text(encoding="utf-8"))

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

    @app.get("/api/status", dependencies=[Depends(require_token)])
    def get_status(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return {
            "mensagem": "Estado atual do sistema recuperado com sucesso.",
            "dados": runtime.describe_state(),
        }

    @app.post("/api/ciclos/executar", dependencies=[Depends(require_token)])
    def run_cycle(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        cycle_result = runtime.run_planner_cycle()
        app.state.last_cycle_result = cycle_result
        return {
            "mensagem": "Ciclo do planejador executado.",
            "resultado": cycle_result,
        }

    @app.get("/api/tarefas", dependencies=[Depends(require_token)])
    def list_tasks(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        tasks = runtime.list_tasks()
        return {
            "mensagem": "Fila atual consultada com sucesso.",
            "total": len(tasks),
            "tarefas": tasks,
        }

    @app.post("/api/tarefas", dependencies=[Depends(require_token)])
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

    @app.get("/api/objetivos", dependencies=[Depends(require_token)])
    def get_goals(request: Request, goal_id: str | None = Query(default=None)) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return {
            "mensagem": "Relatorio de objetivos recuperado.",
            "dados": runtime.get_goal_report(goal_id),
        }

    @app.get("/api/memoria/recente", dependencies=[Depends(require_token)])
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

    @app.get("/api/relatorio", dependencies=[Depends(require_token)])
    def get_report(request: Request) -> Dict[str, Any]:
        runtime = _ensure_runtime_initialized(request)
        return runtime.build_system_report(last_cycle_result=app.state.last_cycle_result)

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
    return runtime


app = create_app()
