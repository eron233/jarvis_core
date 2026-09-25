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
import json
from pathlib import Path
from typing import Annotated, Any, Dict, Optional

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, status
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
from security.access_control import AccessControl

#
# JARVIS_API_LAYER
# JARVIS_SECURITY_GATE
# ==================================================
# BLOCO: Configuracao da API e autenticacao confiavel
# ==================================================

TOKEN_HEADER = "X-Jarvis-Token"
DEVICE_HEADER = "X-Jarvis-Device-Id"
NONCE_HEADER = "X-Jarvis-Nonce"
TIMESTAMP_HEADER = "X-Jarvis-Timestamp"
SESSION_COOKIE = "jarvis_trusted_device"
SIMPLE_WEB_LOGIN_DEVICE_ID = "web-access-recovery"
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


class SimpleWebLoginRequest(BaseModel):
    """Payload minimo do modo de recuperacao de acesso web por senha."""

    admin_password: str = Field(min_length=1)


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
            device_registry_path=effective_deployment_config.device_registry_path,
            cognitive_evolution_storage_path=effective_deployment_config.cognitive_evolution_storage_path,
            audit_storage_path=effective_deployment_config.audit_storage_path,
            self_defense_report_path=effective_deployment_config.self_defense_report_path,
            enable_vital_organs_background=True,
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
    )
    app.state.trusted_device_id = (
        trusted_device_id
        or getattr(effective_deployment_config, "trusted_device_id", None)
    )
    if not app.state.api_token or not app.state.trusted_device_id:
        raise ValueError(
            "A API do JARVIS precisa de token e device id confiavel resolvidos pelo ambiente ou bootstrap seguro."
        )
    access_bootstrap = effective_deployment_config.get_access_bootstrap()
    app.state.simple_web_login = bool(
        getattr(effective_deployment_config, "enable_simple_web_login", False)
    )
    app.state.access_control = AccessControl(
        admin_password_hash=access_bootstrap.admin_password_hash,
        admin_password_salt=access_bootstrap.admin_password_salt,
        admin_password_iterations=access_bootstrap.admin_password_iterations,
        admin_password_source=access_bootstrap.admin_password_source,
    )
    app.state.enable_dashboard = (
        True if effective_deployment_config is None else effective_deployment_config.enable_dashboard
    )
    app.state.environment_report = _build_environment_report(app)
    app.state.runtime.configure_runtime_identity(
        entrypoint="interface.api.app.create_app",
        environment=app.state.environment_report,
        loaded_config={
            "host_api": app.state.environment_report.get("host_api"),
            "porta_api": app.state.environment_report.get("porta_api"),
            "loop_runtime_ativo": app.state.environment_report.get("loop_runtime_ativo"),
            "painel_ativo": app.state.environment_report.get("painel_ativo"),
        },
    )

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
        x_jarvis_nonce: Annotated[str | None, Header(alias=NONCE_HEADER)] = None,
        x_jarvis_timestamp: Annotated[str | None, Header(alias=TIMESTAMP_HEADER)] = None,
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

        if request.app.state.simple_web_login and _has_valid_dashboard_session(request):
            return {
                "device_id": SIMPLE_WEB_LOGIN_DEVICE_ID,
                "access_mode": "simple_web_login",
            }

        return _validate_trusted_access(
            request=request,
            token=x_jarvis_token,
            device_id=x_jarvis_device_id,
            request_nonce=x_jarvis_nonce,
            request_timestamp=x_jarvis_timestamp,
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
            return HTMLResponse(_render_dashboard(request.app))
        return HTMLResponse(_render_access_gate(request.app))

    @app.post("/api/auth/device-session")
    def create_device_session(
        request: Request,
        payload: SimpleWebLoginRequest | None = None,
        x_jarvis_token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
        x_jarvis_device_id: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
        x_jarvis_nonce: Annotated[str | None, Header(alias=NONCE_HEADER)] = None,
        x_jarvis_timestamp: Annotated[str | None, Header(alias=TIMESTAMP_HEADER)] = None,
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

        if request.app.state.simple_web_login:
            access_context = _validate_simple_web_access(
                request=request,
                admin_password=payload.admin_password if payload is not None else None,
            )
            session_cookie_value = _build_simple_web_session_value(
                request.app.state.access_control.admin_password_hash
            )
        else:
            access_context = _validate_trusted_access(
                request=request,
                token=x_jarvis_token,
                device_id=x_jarvis_device_id,
                request_nonce=x_jarvis_nonce,
                request_timestamp=x_jarvis_timestamp,
            )
            session_cookie_value = _build_trusted_session_value(
                request.app.state.api_token,
                access_context["device_id"],
            )
        response = JSONResponse(
            {
                "mensagem": "Acesso ao painel validado com sucesso.",
                "device_id": access_context["device_id"],
                "modo": access_context.get("access_mode", "trusted_device"),
            }
        )
        response.set_cookie(
            key=SESSION_COOKIE,
            value=session_cookie_value,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
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

    @app.get("/api/runtime/identidade", dependencies=[Depends(require_trusted_device)])
    def get_runtime_identity(request: Request) -> Dict[str, Any]:
        """
        Retorna a identidade verificavel do runtime que esta respondendo.

        Parametros:
        - request: requisicao HTTP atual.

        Retorno:
        - commit, boot, entrypoint e configuracao resumida do runtime.

        Efeitos no sistema:
        - nenhum; fornece rastreabilidade do processo ativo.
        """

        runtime = _ensure_runtime_initialized(request)
        return {
            "mensagem": "Identidade do runtime recuperada com sucesso.",
            "dados": runtime.build_runtime_identity_report(),
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

    @app.get("/api/relatorio/sistema", dependencies=[Depends(require_trusted_device)])
    def get_system_report(request: Request) -> Dict[str, Any]:
        """
        Retorna o relatorio operacional resumido oficial do sistema.

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

    @app.get("/api/seguranca/relatorio-semanal", dependencies=[Depends(require_trusted_device)])
    def get_weekly_security_report(request: Request) -> Dict[str, Any]:
        """
        Retorna o relatorio semanal consolidado de seguranca (Bloco 12.6).
        """
        from security.security_report_engine import WeeklySecurityReportEngine
        engine = WeeklySecurityReportEngine()
        latest = engine.load_latest_report()
        if not latest:
            # Gera um no momento se nao existir
            runtime = _ensure_runtime_initialized(request)
            sd_report = runtime.run_self_defense_audit() if hasattr(runtime, "run_self_defense_audit") else {}
            latest = engine.generate_report(self_defense_report=sd_report)
        return {
            "mensagem": "Relatorio semanal de seguranca recuperado com sucesso.",
            "relatorio": latest,
        }

    @app.post("/api/seguranca/relatorio-semanal/gerar", dependencies=[Depends(require_trusted_device)])
    def generate_weekly_security_report(request: Request) -> Dict[str, Any]:
        """
        Forca a geracao de um novo relatorio semanal de seguranca.
        """
        from security.security_report_engine import WeeklySecurityReportEngine
        runtime = _ensure_runtime_initialized(request)
        sd_report = runtime.run_self_defense_audit() if hasattr(runtime, "run_self_defense_audit") else {}
        engine = WeeklySecurityReportEngine()
        report = engine.generate_report(self_defense_report=sd_report)
        return {
            "mensagem": "Relatorio semanal de seguranca gerado e persistido com sucesso.",
            "relatorio": report,
        }

    @app.get("/api/armazenamento/status", dependencies=[Depends(require_trusted_device)])
    def get_storage_status(request: Request) -> Dict[str, Any]:
        """
        Retorna o status do armazenamento transacional SQLite e fallback JSON.
        """
        from executive_planner.transactional_store import TransactionalStore
        tx_store = TransactionalStore()
        return {
            "mensagem": "Status do armazenamento recuperado com sucesso.",
            "armazenamento_transacional": tx_store.get_stats(),
        }

    # --- Endpoints dos 6 Módulos Especializados ---

    @app.post("/api/modulos/autoevolucao/ciclo", dependencies=[Depends(require_trusted_device)])
    def run_auto_evolution_cycle(request: Request) -> Dict[str, Any]:
        """Módulo 1: Executa ciclo de autoevolução e ataque simulado no gêmeo."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.auto_evolution_engine.run_evolution_cycle(runtime=runtime)
        return {"mensagem": "Ciclo de autoevolução executado com sucesso.", "relatorio": res}

    @app.get("/api/modulos/ferramentas", dependencies=[Depends(require_trusted_device)])
    def list_developed_tools(request: Request) -> Dict[str, Any]:
        """Módulo 2: Lista ferramentas e conectores desenvolvidos autonomamente."""
        runtime = _ensure_runtime_initialized(request)
        tools = runtime.tool_developer_engine.list_developed_tools()
        return {"mensagem": "Ferramentas recuperadas com sucesso.", "ferramentas": tools}

    @app.get("/api/modulos/conhecimento", dependencies=[Depends(require_trusted_device)])
    def search_knowledge_base(request: Request, q: str = Query(default="")) -> Dict[str, Any]:
        """Módulo 3: Consulta base de conhecimento comprimida."""
        runtime = _ensure_runtime_initialized(request)
        results = runtime.research_knowledge_engine.search_knowledge(q)
        return {"mensagem": "Pesquisa de conhecimento concluída.", "resultados": results}

    @app.post("/api/modulos/mercado/analisar", dependencies=[Depends(require_trusted_device)])
    def analyze_market_session(request: Request) -> Dict[str, Any]:
        """Módulo 4: Análise de mercado (Mini Dólar / Mini Índice) e fluxo de ordens."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.market_analysis_worker.analyze_market_session(
            asset="WDO",
            price_history=[{"price": 5.15}, {"price": 5.22}],
            flow_data=[{"side": "buy", "volume": 1200}, {"side": "sell", "volume": 800}],
            news_events=[{"timestamp": "10:00", "titulo": "Divulgação Payroll"}],
        )
        return {"mensagem": "Análise de mercado realizada com sucesso.", "analise": res}

    @app.post("/api/modulos/estudio/incubar", dependencies=[Depends(require_trusted_device)])
    def incubate_creative_project(request: Request) -> Dict[str, Any]:
        """Módulo 5: Incuba projeto criativo open-source autossustentável."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.creative_studio_worker.incubate_project(
            project_name="Jarvis Core Open",
            concept="Agente cognitivo determinístico",
            target_market="Desenvolvedores e Empresas",
            competitors=[{"nome": "Framework X", "falhas": ["Falta de determinação", "Código complexo"]}],
        )
        return {"mensagem": "Projeto incubado com sucesso.", "projeto": res}

    @app.get("/api/modulos/dispositivo/perfil", dependencies=[Depends(require_trusted_device)])
    def get_device_profile(request: Request) -> Dict[str, Any]:
        """Módulo 6: Leitura de hardware, perfil do usuário e otimizações simuladas."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.device_profiler.analyze_device_and_profile()
        return {"mensagem": "Perfil do dispositivo gerado com sucesso.", "perfil": res}

    # --- Endpoints de Voz, Automação do SO, Pesquisa Web, Extrator Universal e Feed em Tempo Real ---

    @app.post("/api/voz/falar", dependencies=[Depends(require_trusted_device)])
    def speak_text(request: Request, texto: str = Query(min_length=1)) -> Dict[str, Any]:
        """Sintetiza voz local para resposta audível."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.voice_engine.speak(texto)

    @app.get("/api/sistema/metricas", dependencies=[Depends(require_trusted_device)])
    def get_system_automation_metrics(request: Request) -> Dict[str, Any]:
        """Lê métricas e sensores do SO hospedeiro."""
        runtime = _ensure_runtime_initialized(request)
        return {
            "mensagem": "Métricas do sistema recuperadas.",
            "metricas": runtime.system_automation_engine.get_system_metrics(),
            "processos": runtime.system_automation_engine.list_running_processes(limit=5),
        }

    @app.get("/api/web/pesquisar", dependencies=[Depends(require_trusted_device)])
    def active_web_search(request: Request, q: str = Query(min_length=1)) -> Dict[str, Any]:
        """Realiza pesquisa web ativa e extrai resumos."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.web_browser_engine.search_and_extract(q)

    @app.post("/api/ingestao/universal", dependencies=[Depends(require_trusted_device)])
    def ingest_universal_file(request: Request, caminho_arquivo: str = Query(min_length=1)) -> Dict[str, Any]:
        """Extrai texto e ingere QUALQUER tipo de arquivo no banco SQLite."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.universal_file_extractor.extract_and_ingest_file(caminho_arquivo)

    @app.get("/api/mercado/feed/live", dependencies=[Depends(require_trusted_device)])
    def get_live_market_tick(request: Request) -> Dict[str, Any]:
        """Retorna cotação em tempo real do feed de mercado."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.market_websocket_feed.fetch_live_tick()

    @app.post("/api/modulos/arvore-quantica/explorar", dependencies=[Depends(require_trusted_device)])
    def explore_quantum_tree_hypotheses(request: Request, objetivo: str = Query(min_length=1)) -> Dict[str, Any]:
        """Explora centenas de hipóteses em árvore paralela e submete à validação dos 11 pilares socráticos."""
        runtime = _ensure_runtime_initialized(request)
        initial_hypotheses = [
            {"nome": f"Hipótese Open-Source A", "open_source": True, "custo_estimado_brl": 0.0, "diferencial_inovacao_0_10": 9.2},
            {"nome": f"Hipótese Híbrida Cripto B", "open_source": True, "custo_estimado_brl": 20.0, "diferencial_inovacao_0_10": 9.8},
            {"nome": f"Hipótese Legada C", "open_source": False, "custo_estimado_brl": 200.0, "diferencial_inovacao_0_10": 5.0},
        ]
        res = runtime.quantum_tree_search_engine.explore_hypotheses_tree(
            domain_goal=objetivo,
            initial_hypotheses=initial_hypotheses,
            available_crypto_budget_brl=100.0,
        )
        return {"mensagem": "Exploração de árvore paralela concluída.", "resultado_colapsado": res}

    # --- Endpoints de Arquivos, Visão e Stream de Pensamentos Privados do Dono ---

    @app.post("/api/arquivos/compactar", dependencies=[Depends(require_trusted_device)])
    def compress_files_endpoint(request: Request, caminho: str = Query(min_length=1), formato: str = Query(default="zip")) -> Dict[str, Any]:
        """Compacta arquivos/pastas para .zip, .tar.gz, etc."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.file_archive_engine.compress_files(source_paths=[caminho], format_type=formato)

    @app.post("/api/arquivos/descompactar", dependencies=[Depends(require_trusted_device)])
    def decompress_archive_endpoint(request: Request, caminho: str = Query(min_length=1)) -> Dict[str, Any]:
        """Descompacta e extrai arquivos compactados."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.file_archive_engine.decompress_archive(archive_path=caminho)

    @app.post("/api/visao/analisar-imagem", dependencies=[Depends(require_trusted_device)])
    def analyze_image_endpoint(request: Request, caminho_imagem: str = Query(min_length=1)) -> Dict[str, Any]:
        """Analisa imagem/print, extrai textos (OCR) e cria pré-contexto visual."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.image_vision_engine.analyze_image_and_build_context(image_path=caminho_imagem)

    @app.get("/api/dono/pensamentos-privados")
    def get_owner_private_thoughts(
        request: Request,
        x_jarvis_token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
        x_jarvis_device_id: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    ) -> Dict[str, Any]:
        """
        Retorna o stream de pensamentos privados do JARVIS.
        EXCLUSIVO PARA O DONO AUTENTICADO.
        """
        runtime = _ensure_runtime_initialized(request)
        is_owner = (
            x_jarvis_token == request.app.state.api_token
            and x_jarvis_device_id == request.app.state.trusted_device_id
        )
        return runtime.thought_stream_engine.get_owner_thoughts_stream(is_authenticated_owner=is_owner)

    @app.post("/api/graphify/estruturar", dependencies=[Depends(require_trusted_device)])
    def graphify_project_analysis(request: Request, titulo: str = Query(min_length=1), descricao: str = Query(default="")) -> Dict[str, Any]:
        """Estrutura a análise de um projeto em grafo topológico de nós e arestas."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.graphify_engine.analyze_and_graphify(project_title=titulo, description=descricao)
        return {"mensagem": "Análise topológica Graphify gerada com sucesso.", "resultado": res}

    @app.post("/api/dispositivo/fracionar-carga", dependencies=[Depends(require_trusted_device)])
    def shard_task_load(request: Request, tarefa_id: str = Query(default="t1"), nome_tarefa: str = Query(default="processamento")) -> Dict[str, Any]:
        """Fraciona tarefas pesadas entre os nós registrados para evitar travamento em dispositivos leves."""
        runtime = _ensure_runtime_initialized(request)
        devices = runtime.device_registry.list_devices() if runtime.device_registry else []
        plan = runtime.distributed_task_sharding_engine.evaluate_and_shard_task(
            task_id=tarefa_id,
            task_name=nome_tarefa,
            task_payload={"pesada": True},
            registered_devices=devices,
        )
        return {"mensagem": "Fracionamento de carga avaliado.", "plano_shards": plan}

    # --- Endpoints de Gravação, Filtro DSP e Decodificação de Sinais de Áudio ---

    @app.post("/api/audio/gravar", dependencies=[Depends(require_trusted_device)])
    def start_audio_recording(request: Request, contexto: str = Query(default="aula")) -> Dict[str, Any]:
        """Inicia a gravação de áudio do microfone por tempo intermitente."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.audio_processing_engine.start_intermittent_recording(context_title=contexto)

    @app.post("/api/audio/parar-e-limpar", dependencies=[Depends(require_trusted_device)])
    def stop_and_clean_audio(request: Request) -> Dict[str, Any]:
        """Para a gravação, aplica filtragem DSP de ruídos e retorna áudio limpo + texto."""
        runtime = _ensure_runtime_initialized(request)
        return runtime.audio_processing_engine.stop_and_clean_recording()

    # --- Endpoints JEV (Joint Executive Vector) e Síntese Multi-Domínio ---

    @app.post("/api/decisao/jev/avaliar", dependencies=[Depends(require_trusted_device)])
    def evaluate_jev_decision(request: Request, contexto: str = Query(min_length=1), opcoes: list[Dict[str, Any]] = Body(...)) -> Dict[str, Any]:
        """Avalia opções de decisão usando o Vetor de Decisão Executiva Conjunta (JEV)."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.jev_decision_engine.evaluate_decision_vector(
            decision_context=contexto,
            options=opcoes,
        )
        return {"mensagem": "Avaliação de decisão JEV concluída com sucesso.", "relatorio_jev": res}

    @app.post("/api/sintese/multi-dominio/sintetizar", dependencies=[Depends(require_trusted_device)])
    def synthesize_multi_domain_perspectives(request: Request, topico: str = Query(min_length=1), insumos_dominios: Dict[str, Dict[str, Any]] = Body(...)) -> Dict[str, Any]:
        """Sintetiza visões heterogêneas de múltiplos domínios e resolve conflitos."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.multi_domain_synthesis_engine.synthesize_domain_perspectives(
            topic=topico,
            domain_inputs=insumos_dominios,
        )
        return {"mensagem": "Síntese multi-domínio gerada com sucesso.", "relatorio_sintese": res}

    # --- Endpoints de Caça a Vulnerabilidades por Sub-Agentes, ScrapeGraph, Scrapling MCP e Agent Reach ---

    @app.post("/api/seguranca/caca-vulnerabilidades/campanha", dependencies=[Depends(require_trusted_device)])
    def execute_vulnerability_hunting_campaign(request: Request, nome_alvo: str = Query(min_length=1), caminho_alvo: str = Query(default="src")) -> Dict[str, Any]:
        """Executa campanha de caça a vulnerabilidades (Zero-Days) com sub-agentes e auto-evolução de ferramentas."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.vulnerability_hunter.execute_hunting_campaign(
            target_name=nome_alvo,
            target_codebase_path=caminho_alvo,
        )
        return {"mensagem": "Campanha de caça a vulnerabilidades concluída com sucesso.", "relatorio_campanha": res}

    @app.post("/api/web/scrapegraph/extrair", dependencies=[Depends(require_trusted_device)])
    def extract_structured_scrapegraph(request: Request, url: str = Query(min_length=1), html: str = Body(...), schema: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        """Realiza extração adaptativa por grafo semântico sem seletores CSS rígidos."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.scrapegraph_engine.extract_structured_graph(
            target_url=url,
            html_content=html,
            extraction_schema=schema,
        )
        return {"mensagem": "Extração adaptativa ScrapeGraph concluída com sucesso.", "resultado_grafo": res}

    @app.post("/api/web/scrapling-mcp/raspagem-stealth", dependencies=[Depends(require_trusted_device)])
    def scrape_stealth_mcp_endpoint(request: Request, url: str = Query(min_length=1), nivel_stealth: str = Query(default="high")) -> Dict[str, Any]:
        """Executa raspagem stealth e empacota no formato padrão do protocolo MCP."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.scrapling_mcp_engine.scrape_stealth_mcp(
            target_url=url,
            stealth_level=nivel_stealth,
        )
        return {"mensagem": "Raspagem stealth MCP concluída com sucesso.", "pacote_mcp": res}

    @app.post("/api/learning/agent-reach/contexto", dependencies=[Depends(require_trusted_device)])
    def reach_multi_source_context_endpoint(request: Request, topico: str = Query(min_length=1)) -> Dict[str, Any]:
        """Realiza varredura multi-fonte para agregação e validação cruzada de contexto profundo."""
        runtime = _ensure_runtime_initialized(request)
        res = runtime.agent_reach_engine.reach_multi_source_context(topic_query=topico)
        return {"mensagem": "Agregação de contexto do Agent Reach concluída com sucesso.", "relatorio_alcance": res}

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
        deployment_config=request.app.state.deployment_config,
    )
    request.app.state.runtime = runtime
    request.app.state.bootstrap_state = bootstrap_state
    request.app.state.environment_report = _build_environment_report(request.app)
    return runtime


def _validate_trusted_access(
    request: Request,
    token: str | None,
    device_id: str | None,
    request_nonce: str | None = None,
    request_timestamp: str | None = None,
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

    if _requires_replay_protection(request):
        replay_reason = _validate_replay_headers(
            runtime=runtime,
            request=request,
            device_id=device_id,
            request_nonce=request_nonce,
            request_timestamp=request_timestamp,
        )
        if replay_reason is not None:
            _record_access_attempt(runtime, request, device_id, False, replay_reason, client_host)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_map_replay_error_to_detail(replay_reason),
            )

    _record_access_attempt(runtime, request, device_id, True, None, client_host)
    return {"device_id": device_id}


def _validate_simple_web_access(
    request: Request,
    admin_password: str | None,
) -> Dict[str, str]:
    """
    Valida o modo emergencial de acesso web por senha administrativa.

    Parametros:
    - request: requisicao HTTP atual.
    - admin_password: senha informada no formulario simplificado.

    Retorno:
    - contexto sintetico de acesso ao painel.

    Efeitos no sistema:
    - registra tentativas de recuperacao de acesso no backend.
    """

    runtime = _ensure_runtime_initialized(request)
    client_host = request.client.host if request.client is not None else None

    if not admin_password:
        _record_access_attempt(
            runtime,
            request,
            SIMPLE_WEB_LOGIN_DEVICE_ID,
            False,
            "simple_web_login_missing_password",
            client_host,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha administrativa ausente.",
        )

    access_context = request.app.state.access_control.evaluate(password=admin_password)
    if not access_context.get("admin_access"):
        _record_access_attempt(
            runtime,
            request,
            SIMPLE_WEB_LOGIN_DEVICE_ID,
            False,
            "simple_web_login_invalid_password",
            client_host,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha administrativa invalida.",
        )

    _record_access_attempt(runtime, request, SIMPLE_WEB_LOGIN_DEVICE_ID, True, None, client_host)
    return {
        "device_id": SIMPLE_WEB_LOGIN_DEVICE_ID,
        "access_mode": "simple_web_login",
    }


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

    if request.app.state.simple_web_login:
        expected_value = _build_simple_web_session_value(
            request.app.state.access_control.admin_password_hash
        )
    else:
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


def _build_simple_web_session_value(admin_password_hash: str) -> str:
    """
    Gera o valor do cookie do modo emergencial de acesso web.

    Parametros:
    - admin_password_hash: hash PBKDF2 da senha administrativa efetiva.

    Retorno:
    - valor estavel e nao reversivel para a sessao do painel.
    """

    return hashlib.sha256(f"simple-web:{admin_password_hash}".encode("utf-8")).hexdigest()


def _render_access_gate(app: FastAPI) -> str:
    """
    Renderiza a tela de acesso com o modo efetivo de autenticacao.

    Parametros:
    - app: instancia atual da API.

    Retorno:
    - HTML final da tela de acesso.
    """

    gate_config = {"simple_web_login": bool(app.state.simple_web_login)}
    return ACCESS_GATE_PATH.read_text(encoding="utf-8").replace(
        "__JARVIS_GATE_CONFIG__",
        json.dumps(gate_config, ensure_ascii=False),
    )


def _render_dashboard(app: FastAPI) -> str:
    """
    Renderiza o painel com a configuracao de login ativa no navegador.

    Parametros:
    - app: instancia atual da API.

    Retorno:
    - HTML final do painel.
    """

    dashboard_config = {"simple_web_login": bool(app.state.simple_web_login)}
    return DASHBOARD_PATH.read_text(encoding="utf-8").replace(
        "__JARVIS_DASHBOARD_CONFIG__",
        json.dumps(dashboard_config, ensure_ascii=False),
    )


def _requires_replay_protection(request: Request) -> bool:
    """
    Informa se a rota atual exige nonce e timestamp para reduzir replay.

    Parametros:
    - request: requisicao HTTP atual.

    Retorno:
    - `True` quando a chamada muta estado ou executa acao sensivel.

    Efeitos no sistema:
    - nenhum; usado pela camada de autenticacao HTTP.
    """

    return request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}


def _validate_replay_headers(
    runtime: InternalAgentRuntime,
    request: Request,
    device_id: str,
    request_nonce: str | None,
    request_timestamp: str | None,
) -> str | None:
    """
    Valida nonce e timestamp de chamadas mutantes para reduzir replay simples.

    Parametros:
    - runtime: runtime compartilhado da aplicacao.
    - request: requisicao HTTP atual.
    - device_id: dispositivo confiavel ja validado.
    - request_nonce: nonce enviado pelo cliente.
    - request_timestamp: timestamp enviado pelo cliente.

    Retorno:
    - `None` quando a protecao passou, ou o motivo tecnico da negacao.

    Efeitos no sistema:
    - registra o nonce observado em memoria do runtime.
    """

    if not request_nonce:
        return "missing_request_nonce"
    if not request_timestamp:
        return "missing_request_timestamp"

    try:
        request_dt = _parse_request_timestamp(request_timestamp)
    except ValueError:
        return "invalid_request_timestamp"

    age_seconds = abs((datetime.now(timezone.utc) - request_dt).total_seconds())
    if age_seconds > 120:
        return "stale_request_timestamp"

    accepted, reason = runtime.validate_request_replay(
        device_id=device_id,
        request_path=request.url.path,
        request_method=request.method,
        request_timestamp=request_timestamp,
        request_nonce=request_nonce,
    )
    if not accepted:
        return reason or "replay_detected"
    return None


def _parse_request_timestamp(value: str) -> datetime:
    """Converte timestamp HTTP do cliente para `datetime` UTC."""

    normalized = str(value).strip()
    if normalized.isdigit():
        numeric_value = int(normalized)
        if len(normalized) >= 13:
            return datetime.fromtimestamp(numeric_value / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(numeric_value, tz=timezone.utc)

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp invalido") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _map_replay_error_to_detail(reason: str) -> str:
    """Traduz o motivo tecnico de replay para uma mensagem HTTP clara."""

    messages = {
        "missing_request_nonce": "Nonce de requisicao ausente.",
        "missing_request_timestamp": "Timestamp de requisicao ausente.",
        "invalid_request_timestamp": "Timestamp de requisicao invalido.",
        "stale_request_timestamp": "Timestamp de requisicao expirado.",
        "replay_detected": "Requisicao repetida detectada.",
    }
    return messages.get(reason, "Requisicao negada pela camada anti-replay.")


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
            "audit_storage_path": str(getattr(app.state.system_config, "audit_storage_path", "")),
            "device_registry_path": str(getattr(app.state.system_config, "device_registry_path", "")),
            "self_defense_report_path": str(getattr(app.state.system_config, "self_defense_report_path", "")),
        },
        "autenticacao_configurada": {
            "token_configurado": _is_runtime_secret_configured(app.state.api_token, DEFAULT_API_TOKEN),
            "dispositivo_confiavel_configurado": _is_runtime_secret_configured(
                app.state.trusted_device_id,
                DEFAULT_TRUSTED_DEVICE_ID,
            ),
            "protecao_anti_replay_mutante": True,
        },
    }


app = create_app(config=SystemLoopConfig(enable_vital_organs_background=True))
