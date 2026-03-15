"""
JARVIS - API de Controle

Responsavel por:
- expor o runtime por HTTP em endpoints seguros
- proteger acesso por token e dispositivo confiavel
- servir o painel web e os relatorios operacionais

Integracoes principais:
- runtime.internal_agent_runtime
- runtime.system_config
- executive_planner
- interface.dashboard
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main import SystemLoopConfig, bootstrap_runtime
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.system_config import (
    DEFAULT_API_TOKEN,
    DEFAULT_TRUSTED_DEVICE_ID,
    JarvisEnvironmentConfig,
)

#
# JARVIS_API_LAYER
# JARVIS_SECURITY_GATE
# ==================================================
# BLOCO: Configuracao da API e autenticacao confiavel
# ==================================================

TOKEN_HEADER = "X-Jarvis-Token"
DEVICE_HEADER = "X-Jarvis-Device-Id"
SESSION_COOKIE = "jarvis_trusted_device"
SAFE_WORKER_IDS = {"runtime", "finance", "study", "studio"}
DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "index.html"
ACCESS_GATE_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "access_gate.html"
BRAIN_AVATAR_DIR = Path(__file__).resolve().parents[1] / "brain_avatar"


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


class CommandRequest(BaseModel):
    """Payload minimo do canal textual de comandos do Jarvis."""

    texto: str = Field(min_length=1)
    voz_identificada: Optional[str] = None
    senha: Optional[str] = None
    modo_resposta: str = Field(default="conversacional")


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
            cognitive_evolution_storage_path=effective_deployment_config.cognitive_evolution_storage_path,
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

    if BRAIN_AVATAR_DIR.exists():
        app.mount(
            "/brain-avatar",
            StaticFiles(directory=BRAIN_AVATAR_DIR),
            name="brain_avatar",
        )

    def require_trusted_device(
        request: Request,
        x_jarvis_token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
        x_jarvis_device_id: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    ) -> Dict[str, str]:
        """
        Valida token e device id antes de liberar endpoints protegidos.

        Parametros:
        - request: requisicao HTTP atual.
        - x_jarvis_token: token enviado no header.
        - x_jarvis_device_id: identificador do dispositivo confiavel.

        Retorno:
        - contexto minimo do dispositivo autorizado.

        Efeitos no sistema:
        - registra acessos autorizados e negados na auditoria do runtime.
        """

        return _validate_trusted_access(
            request=request,
            token=x_jarvis_token,
            device_id=x_jarvis_device_id,
        )

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """
        Redireciona a raiz da API para o painel web.

        Parametros:
        - nenhum.

        Retorno:
        - resposta HTTP de redirecionamento.

        Efeitos no sistema:
        - nenhum; apenas melhora o acesso manual ao painel.
        """

        return RedirectResponse(url="/painel", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @app.get("/painel", include_in_schema=False, response_class=HTMLResponse)
    def get_dashboard(request: Request) -> HTMLResponse:
        """
        Entrega o painel ou a tela de acesso, dependendo da sessao.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - HTML do painel ou do gate de acesso.

        Efeitos no sistema:
        - nenhum direto; usa cookie de sessao e configuracao do painel.
        """

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
        """
        Cria a sessao HTTP do dispositivo confiavel no navegador.

        Parametros:
        - request: requisicao HTTP atual.
        - x_jarvis_token: token do Jarvis.
        - x_jarvis_device_id: identificador do dispositivo autorizado.

        Retorno:
        - resposta JSON com cookie de sessao configurado.

        Efeitos no sistema:
        - grava a validacao do acesso e prepara o painel autenticado.
        """

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
        """
        Remove a sessao HTTP do dispositivo autenticado.

        Parametros:
        - nenhum.

        Retorno:
        - resposta JSON confirmando a limpeza do cookie.

        Efeitos no sistema:
        - encerra a sessao local do painel.
        """

        response = JSONResponse({"mensagem": "Sessao do dispositivo removida."})
        response.delete_cookie(SESSION_COOKIE)
        return response

    @app.get("/api/saude")
    def healthcheck(request: Request) -> Dict[str, Any]:
        """
        Retorna um healthcheck simples e publico da API.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - status basico do runtime e do momento de subida da API.

        Efeitos no sistema:
        - inicializa o runtime se necessario para refletir estado atual.
        """

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
        """
        Retorna um healthcheck de deploy sem exigir autenticacao.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - payload rico de saude do ambiente e do runtime.

        Efeitos no sistema:
        - inicializa o runtime se necessario para responder o estado real.
        """

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
        """
        Retorna o healthcheck rico em endpoint autenticado.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - relatorio completo de saude do sistema.

        Efeitos no sistema:
        - nenhum adicional alem da leitura do estado operacional.
        """

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
        """
        Recupera o estado atual resumido do runtime.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - resumo do runtime pronto para consumo externo.

        Efeitos no sistema:
        - nenhum; apenas leitura do estado compartilhado.
        """

        runtime = _ensure_runtime_initialized(request)
        return {
            "mensagem": "Estado atual do sistema recuperado com sucesso.",
            "dados": runtime.describe_state(),
        }

    @app.post("/api/ciclos/executar", dependencies=[Depends(require_trusted_device)])
    def run_cycle(request: Request) -> Dict[str, Any]:
        """
        Dispara um ciclo do planner a partir da API.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - resultado do ciclo executado.

        Efeitos no sistema:
        - executa planejamento, dispatch e persistencia associados ao ciclo.
        """

        runtime = _ensure_runtime_initialized(request)
        cycle_result = runtime.run_planner_cycle()
        app.state.last_cycle_result = cycle_result
        return {
            "mensagem": "Ciclo do planejador executado.",
            "resultado": cycle_result,
        }

    @app.post("/api/comando")
    def execute_command(
        payload: CommandRequest,
        request: Request,
        trusted_access: Dict[str, str] = Depends(require_trusted_device),
    ) -> Dict[str, Any]:
        """
        Encaminha um comando textual autenticado para o runtime do Jarvis.

        Parametros:
        - payload: comando textual e contexto leve de acesso.
        - request: requisicao HTTP atual.
        - trusted_access: dispositivo validado pela camada HTTP.

        Retorno:
        - resposta textual e tecnica do runtime.

        Efeitos no sistema:
        - registra o comando, pode executar um ciclo e pode disparar autodiagnostico seguro.
        """

        runtime = _ensure_runtime_initialized(request)
        result = runtime.handle_command(
            text=payload.texto,
            voice_id=payload.voz_identificada,
            password=payload.senha,
            source_device_id=trusted_access["device_id"],
            response_mode=payload.modo_resposta,
            environment_report=_build_environment_report(request.app),
        )
        result["mensagem"] = "Comando processado com sucesso."
        return result

    @app.get("/api/tarefas", dependencies=[Depends(require_trusted_device)])
    def list_tasks(request: Request) -> Dict[str, Any]:
        """
        Lista a fila atual de tarefas do sistema.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - quantidade e tarefas atualmente enfileiradas.

        Efeitos no sistema:
        - nenhum; consulta a fila compartilhada do runtime.
        """

        runtime = _ensure_runtime_initialized(request)
        tasks = runtime.list_tasks()
        return {
            "mensagem": "Fila atual consultada com sucesso.",
            "total": len(tasks),
            "tarefas": tasks,
        }

    @app.post("/api/tarefas", dependencies=[Depends(require_trusted_device)])
    def add_task(payload: TaskCreateRequest, request: Request) -> Dict[str, Any]:
        """
        Adiciona uma nova tarefa autenticada na fila do Jarvis.

        Parametros:
        - payload: corpo da tarefa a ser enfileirada.
        - request: requisicao HTTP atual.

        Retorno:
        - confirmacao com a tarefa normalizada.

        Efeitos no sistema:
        - insere uma nova tarefa persistente na fila do runtime.
        """

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
        """
        Retorna o relatorio de objetivos ou de um objetivo especifico.

        Parametros:
        - request: requisicao HTTP atual.
        - goal_id: identificador opcional do objetivo desejado.

        Retorno:
        - relatorio da camada de intencao em pt-BR.

        Efeitos no sistema:
        - nenhum; apenas leitura do GoalManager.
        """

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
        """
        Recupera memoria semantica e episodica recente.

        Parametros:
        - request: requisicao HTTP atual.
        - limit: quantidade maxima por lista retornada.
        - domain: dominio opcional para filtrar memoria semantica.

        Retorno:
        - entradas semanticas e eventos episodicos recentes.

        Efeitos no sistema:
        - nenhum; apenas leitura das memorias do runtime.
        """

        runtime = _ensure_runtime_initialized(request)
        semantic_entries = runtime.get_recent_semantic_entries(limit=limit, domain=domain)
        recent_events = runtime.get_recent_events(limit=limit)
        return {
            "mensagem": "Memoria recente recuperada.",
            "entradas_semanticas": semantic_entries,
            "eventos_episodicos": recent_events,
        }

    @app.get("/api/cognicao/evolucao", dependencies=[Depends(require_trusted_device)])
    def get_cognitive_evolution(
        request: Request,
        nivel: str = Query(default="historica"),
    ) -> Dict[str, Any]:
        """
        Retorna o payload visual do mapa evolutivo cognitivo.

        Parametros:
        - request: requisicao HTTP atual.
        - nivel: recorte temporal desejado para a evolucao.

        Retorno:
        - dados de visualizacao e resumo do crescimento cognitivo.

        Efeitos no sistema:
        - nenhum; apenas leitura do historico cognitivo.
        """

        runtime = _ensure_runtime_initialized(request)
        return runtime.build_cognitive_evolution_report(level=nivel)

    @app.get("/api/cognicao/evolucao/analise", dependencies=[Depends(require_trusted_device)])
    def get_cognitive_evolution_analysis(
        request: Request,
        nivel: str = Query(default="historica"),
    ) -> Dict[str, Any]:
        """
        Retorna a analise interna do historico evolutivo cognitivo.

        Parametros:
        - request: requisicao HTTP atual.
        - nivel: recorte temporal desejado para a analise.

        Retorno:
        - sintese das regioes e trilhas cognitivas mais relevantes.

        Efeitos no sistema:
        - nenhum; apenas consulta do historico cognitivo.
        """

        runtime = _ensure_runtime_initialized(request)
        return runtime.build_cognitive_evolution_analysis(level=nivel)

    @app.get("/api/relatorio", dependencies=[Depends(require_trusted_device)])
    def get_report(request: Request) -> Dict[str, Any]:
        """
        Retorna o relatorio operacional resumido do sistema.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - relatorio consolidado do runtime com ambiente.

        Efeitos no sistema:
        - nenhum; usa o ultimo ciclo conhecido para montar a resposta.
        """

        runtime = _ensure_runtime_initialized(request)
        report = runtime.build_system_report(last_cycle_result=app.state.last_cycle_result)
        report["ambiente"] = _build_environment_report(request.app)
        return report

    @app.get("/api/relatorio/sistema", dependencies=[Depends(require_trusted_device)])
    def get_system_report(request: Request) -> Dict[str, Any]:
        """
        Alias autenticado para o relatorio geral do sistema.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - relatorio consolidado do runtime com ambiente.

        Efeitos no sistema:
        - nenhum; reaproveita a mesma construcao de relatorio.
        """

        runtime = _ensure_runtime_initialized(request)
        report = runtime.build_system_report(last_cycle_result=app.state.last_cycle_result)
        report["ambiente"] = _build_environment_report(request.app)
        return report

    @app.get("/api/relatorio/fila", dependencies=[Depends(require_trusted_device)])
    def get_queue_report(request: Request) -> Dict[str, Any]:
        """
        Retorna o relatorio operacional da fila.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - resumo e lista de tarefas do estado atual da fila.

        Efeitos no sistema:
        - nenhum; apenas leitura do runtime.
        """

        runtime = _ensure_runtime_initialized(request)
        return runtime.build_queue_report()

    @app.get("/api/relatorio/objetivos", dependencies=[Depends(require_trusted_device)])
    def get_goals_report(request: Request) -> Dict[str, Any]:
        """
        Retorna o relatorio operacional da camada de objetivos.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - metas estrategicas, objetivos ativos e resumo.

        Efeitos no sistema:
        - nenhum; apenas leitura da camada de intencao.
        """

        runtime = _ensure_runtime_initialized(request)
        return runtime.build_goal_operational_report()

    @app.get("/api/relatorio/memoria", dependencies=[Depends(require_trusted_device)])
    def get_memory_report(request: Request) -> Dict[str, Any]:
        """
        Retorna o relatorio operacional das memorias do sistema.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - resumo da memoria semantica e procedural.

        Efeitos no sistema:
        - nenhum; apenas leitura do runtime.
        """

        runtime = _ensure_runtime_initialized(request)
        return runtime.build_memory_report()

    @app.get("/api/relatorio/auditoria", dependencies=[Depends(require_trusted_device)])
    def get_audit_report(request: Request) -> Dict[str, Any]:
        """
        Retorna o relatorio consolidado de auditoria.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - ultimos acessos, decisoes do planner e falhas registradas.

        Efeitos no sistema:
        - nenhum; apenas consulta de rastreabilidade.
        """

        runtime = _ensure_runtime_initialized(request)
        return runtime.build_audit_report()

    return app


def _resolve_worker(requested_worker: str | None, domain: str) -> str:
    """
    Resolve o worker final a partir do dominio quando necessario.

    Parametros:
    - requested_worker: worker explicitamente informado na requisicao.
    - domain: dominio funcional da tarefa.

    Retorno:
    - identificador de worker a ser usado no runtime.

    Efeitos no sistema:
    - nenhum; padroniza o roteamento de tarefas vindas da API.
    """

    if requested_worker:
        return requested_worker
    if domain in SAFE_WORKER_IDS:
        return f"worker_{domain}"
    return "worker_runtime"


def _ensure_runtime_initialized(request: Request) -> InternalAgentRuntime:
    """
    Garante que a aplicacao compartilhe um runtime inicializado.

    Parametros:
    - request: requisicao HTTP atual.

    Retorno:
    - runtime pronto para responder a chamada.

    Efeitos no sistema:
    - pode executar o bootstrap do runtime na primeira requisicao.
    """

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
    """
    Valida token e device id para acesso protegido.

    Parametros:
    - request: requisicao HTTP atual.
    - token: token recebido no header.
    - device_id: identificador do dispositivo no header.

    Retorno:
    - contexto minimo do dispositivo autorizado.

    Efeitos no sistema:
    - registra todas as tentativas na auditoria do runtime.
    """

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

    if runtime.device_registry is not None:
        runtime.device_registry.ensure_device(
            device_id=request.app.state.trusted_device_id,
            nome="dispositivo_principal_api",
            tipo="client",
            trusted=True,
            primary=True,
            metadata={"source": "api_security_gate"},
        )

    trusted_device = device_id == request.app.state.trusted_device_id or (
        runtime.device_registry is not None and runtime.device_registry.is_trusted(device_id)
    )

    if not trusted_device:
        _record_access_attempt(runtime, request, device_id, False, "untrusted_device", client_host)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dispositivo nao autorizado.",
        )

    if runtime.device_registry is not None:
        runtime.device_registry.ensure_device(
            device_id=device_id,
            nome=device_id,
            tipo="client",
            trusted=True,
            primary=device_id == request.app.state.trusted_device_id,
            metadata={"last_client_host": client_host or "desconhecido"},
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
    """
    Encaminha um evento de acesso para a auditoria do runtime.

    Parametros:
    - runtime: runtime compartilhado da aplicacao.
    - request: requisicao associada ao acesso.
    - device_id: identificador enviado pelo cliente.
    - allowed: indicador de autorizacao.
    - reason: motivo opcional da negacao.
    - client_host: host remoto informado pelo cliente.

    Retorno:
    - nenhum.

    Efeitos no sistema:
    - grava eventos de acesso no runtime e na memoria episodica.
    """

    runtime.record_access_attempt(
        endpoint=request.url.path,
        method=request.method,
        device_id=device_id,
        allowed=allowed,
        reason=reason,
        client_host=client_host,
    )


def _has_valid_dashboard_session(request: Request) -> bool:
    """
    Verifica se o cookie do painel corresponde ao dispositivo confiavel.

    Parametros:
    - request: requisicao HTTP atual.

    Retorno:
    - `True` quando a sessao do painel esta valida.

    Efeitos no sistema:
    - nenhum; protege o HTML do painel.
    """

    session_value = request.cookies.get(SESSION_COOKIE)
    if not session_value:
        return False

    expected_value = _build_trusted_session_value(
        request.app.state.api_token,
        request.app.state.trusted_device_id,
    )
    return session_value == expected_value


def _build_trusted_session_value(api_token: str, device_id: str) -> str:
    """
    Gera o valor hasheado da sessao de dispositivo confiavel.

    Parametros:
    - api_token: token configurado da API.
    - device_id: dispositivo confiavel ativo.

    Retorno:
    - hash SHA-256 usado como cookie de sessao.

    Efeitos no sistema:
    - nenhum; padroniza a protecao do painel.
    """

    return hashlib.sha256(f"{api_token}:{device_id}".encode("utf-8")).hexdigest()


def _is_runtime_secret_configured(value: str | None, default_value: str) -> bool:
    """
    Informa se um segredo configurado difere do valor padrao inseguro.

    Parametros:
    - value: valor atual carregado na aplicacao.
    - default_value: valor padrao conhecido do sistema.

    Retorno:
    - `True` quando o segredo foi configurado explicitamente.

    Efeitos no sistema:
    - nenhum; alimenta healthcheck e relatorio de ambiente.
    """

    return bool(value) and value != default_value


def _build_environment_report(app: FastAPI) -> Dict[str, Any]:
    """
    Monta um resumo seguro do ambiente atual da aplicacao.

    Parametros:
    - app: instancia FastAPI com estado compartilhado.

    Retorno:
    - dicionario resumido de ambiente, paths e autenticacao.

    Efeitos no sistema:
    - nenhum; usado em healthchecks e relatorios.
    """

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
            "device_registry_path": str(getattr(app.state.system_config, "device_registry_path", "")),
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
