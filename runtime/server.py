"""
JARVIS - Servidor de Runtime

Responsavel por:
- inicializar o contexto de deploy do Jarvis
- subir a API HTTP e o loop continuo opcional
- registrar startup, shutdown e relatorios de ambiente

Integracoes principais:
- runtime.system_config
- runtime.internal_agent_runtime
- interface.api.app
- main
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from threading import Thread
from typing import Any, Dict, Optional

#
# JARVIS_RUNTIME_ENTRYPOINT
# ==================================================
# BLOCO: Bootstrap do servidor e do loop continuo
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from startup_bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from interface.api.app import create_app
from main import JarvisSystemLoop, SystemLoopConfig, bootstrap_runtime
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.system_config import JarvisEnvironmentConfig


class RuntimeLoopWorker:
    """Executa o loop continuo do JARVIS em uma thread controlada."""

    def __init__(
        self,
        runtime: InternalAgentRuntime,
        config: SystemLoopConfig,
        logger: logging.Logger,
    ) -> None:
        """
        Prepara um executor em thread para o loop continuo do Jarvis.

        Parametros:
        - runtime: runtime compartilhado com a API.
        - config: configuracao do loop continuo.
        - logger: logger usado para mensagens de operacao.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - instancia o loop que podera ser iniciado em background.
        """

        self.logger = logger
        self.loop = JarvisSystemLoop(
            runtime=runtime,
            config=config,
            logger=self._log,
        )
        self.thread: Thread | None = None
        self.last_summary: Dict[str, Any] | None = None

    def start(self) -> None:
        """
        Inicia a thread do loop continuo se ainda nao estiver ativa.

        Parametros:
        - nenhum.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - dispara a execucao em background do loop do runtime.
        """

        if self.thread is not None and self.thread.is_alive():
            return

        self.thread = Thread(
            target=self._run_loop,
            name="jarvis-runtime-loop",
            daemon=True,
        )
        self.thread.start()

    def stop(self, reason: str = "requested", join_timeout: float = 30.0) -> Dict[str, Any] | None:
        """
        Solicita o encerramento do loop continuo e aguarda a thread.

        Parametros:
        - reason: motivo textual do encerramento.
        - join_timeout: tempo maximo de espera pela parada da thread.

        Retorno:
        - ultimo resumo do loop, quando disponivel.

        Efeitos no sistema:
        - encerra de forma controlada o loop em background.
        """

        if self.thread is None:
            return self.last_summary

        self.loop.request_shutdown(reason)
        self.thread.join(join_timeout)

        if self.thread.is_alive():
            self.logger.warning("[shutdown] loop continuo ainda nao encerrou apos %.1f segundo(s).", join_timeout)

        return deepcopy(self.last_summary)

    def _run_loop(self) -> None:
        """
        Executa o loop continuo e armazena seu ultimo resumo.

        Parametros:
        - nenhum.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - atualiza `last_summary` com o resultado do loop.
        """

        self.last_summary = self.loop.run()

    def _log(self, message: str) -> None:
        """
        Encaminha mensagens do loop para o logger do servidor.

        Parametros:
        - message: texto emitido pelo loop continuo.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - grava logs operacionais do loop em saida e arquivo.
        """

        self.logger.info(message)


class JarvisServerContext:
    """Contexto de execucao do servidor do JARVIS."""

    def __init__(
        self,
        config: JarvisEnvironmentConfig,
        runtime: InternalAgentRuntime | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Cria o contexto compartilhado entre servidor HTTP e runtime.

        Parametros:
        - config: configuracao central do ambiente.
        - runtime: runtime opcional para injecao em testes.
        - logger: logger opcional previamente configurado.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - prepara o estado usado no bootstrap, loop e shutdown.
        """

        self.config = config
        self.runtime = runtime or InternalAgentRuntime()
        self.logger = logger or configure_logging(config)
        self.bootstrap_state: Dict[str, Any] | None = None
        self.loop_worker: RuntimeLoopWorker | None = None

    def bootstrap(self) -> Dict[str, Any]:
        """Inicializa a persistencia, o runtime e grava o relatorio de ambiente."""

        if self.bootstrap_state is not None:
            return deepcopy(self.bootstrap_state)

        self.config.validate()
        self.config.ensure_directories()
        self.bootstrap_state = bootstrap_runtime(
            runtime=self.runtime,
            config=self.build_loop_config(install_signal_handlers=False),
            logger=self.logger.info,
        )[1]
        self._write_report(
            self.config.startup_report_path,
            {
                "timestamp": self._utc_now(),
                "mensagem": "Resumo de ambiente do deploy do JARVIS.",
                "ambiente": self.config.build_environment_report(),
                "runtime": self.runtime.describe_state(),
                "bootstrap": self.bootstrap_state,
            },
        )
        self.logger.info(
            "[startup] ambiente=%s host=%s porta=%s loop_ativo=%s painel_ativo=%s",
            self.config.env,
            self.config.api_host,
            self.config.api_port,
            self.config.enable_runtime_loop,
            self.config.enable_dashboard,
        )
        return deepcopy(self.bootstrap_state)

    def build_app(self):
        """Constroi a aplicacao HTTP compartilhando o runtime ja bootstrapado."""

        bootstrap_state = self.bootstrap()
        app = create_app(
            runtime=self.runtime,
            api_token=self.config.token,
            trusted_device_id=self.config.trusted_device_id,
            config=self.build_loop_config(install_signal_handlers=False),
            deployment_config=self.config,
        )
        app.state.bootstrap_state = deepcopy(bootstrap_state)
        app.state.environment_report = self.config.build_environment_report()
        return app

    def start_runtime_loop(self) -> None:
        """Inicia o loop continuo do runtime quando configurado."""

        if not self.config.enable_runtime_loop:
            self.logger.info("[startup] loop continuo desabilitado por configuracao.")
            return

        if self.loop_worker is None:
            self.loop_worker = RuntimeLoopWorker(
                runtime=self.runtime,
                config=self.build_loop_config(install_signal_handlers=False),
                logger=self.logger,
            )

        self.loop_worker.start()
        self.logger.info("[startup] loop continuo iniciado em background.")

    def shutdown(self, reason: str = "requested") -> Dict[str, Any]:
        """Encerra o loop continuo e persiste um resumo final do runtime."""

        loop_summary = None
        if self.loop_worker is not None:
            loop_summary = self.loop_worker.stop(reason=reason)

        persisted_state = self.runtime.persist_runtime_state()
        shutdown_report = {
            "timestamp": self._utc_now(),
            "motivo": reason,
            "ambiente": self.config.build_environment_report(),
            "runtime": self.runtime.describe_state(),
            "persistencia": persisted_state,
            "loop": loop_summary,
        }
        self._write_report(self.config.shutdown_report_path, shutdown_report)
        self.logger.info("[shutdown] estado persistido com sucesso em %s.", self.config.shutdown_report_path)
        return shutdown_report

    def build_loop_config(self, install_signal_handlers: bool = False) -> SystemLoopConfig:
        """Traduz a configuracao central para a configuracao do loop."""

        return SystemLoopConfig(
            cycle_sleep_seconds=self.config.loop_interval_seconds,
            idle_sleep_seconds=self.config.idle_sleep_seconds,
            install_signal_handlers=install_signal_handlers,
            queue_storage_path=self.config.queue_storage_path,
            semantic_storage_path=self.config.semantic_storage_path,
            procedural_storage_path=self.config.procedural_storage_path,
            goal_storage_path=self.config.goals_storage_path,
            cognitive_evolution_storage_path=self.config.cognitive_evolution_storage_path,
        )

    def _write_report(self, path: Path, payload: Dict[str, Any]) -> None:
        """
        Persiste um relatorio operacional em JSON.

        Parametros:
        - path: arquivo de destino.
        - payload: conteudo serializavel do relatorio.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - escreve relatórios de startup ou shutdown em disco.
        """

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _utc_now() -> str:
        """
        Gera um timestamp UTC em formato ISO 8601.

        Parametros:
        - nenhum.

        Retorno:
        - string temporal padronizada.

        Efeitos no sistema:
        - nenhum; utilitario de carimbo temporal do servidor.
        """

        return datetime.now(timezone.utc).isoformat()


def configure_logging(config: JarvisEnvironmentConfig) -> logging.Logger:
    """Prepara logging em arquivo e stdout para deploy simples."""

    config.ensure_directories()

    logger = logging.getLogger("jarvis.server")
    logger.setLevel(getattr(logging, config.log_level, logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(config.log_file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


def run_server(config: JarvisEnvironmentConfig | None = None) -> int:
    """Sobe o servidor HTTP do JARVIS com o loop continuo opcional."""

    config = config or JarvisEnvironmentConfig.from_env()
    logger = configure_logging(config)
    context = JarvisServerContext(config=config, logger=logger)
    app = context.build_app()
    context.start_runtime_loop()

    logger.info("[startup] API do JARVIS pronta para responder em http://%s:%s", config.api_host, config.api_port)

    try:
        import uvicorn

        uvicorn.run(
            app,
            host=config.api_host,
            port=config.api_port,
            log_level=config.log_level.lower(),
        )
    finally:
        context.shutdown(reason="requested")

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    """Monta o parser do entrypoint do servidor."""

    parser = argparse.ArgumentParser(description="Sobe o servidor HTTP do JARVIS.")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Valida a configuracao do ambiente e imprime um resumo sem subir a API.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do servidor para deploy em VPS simples."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        config = JarvisEnvironmentConfig.from_env()
    except ValueError as exc:
        print(str(exc))
        return 2

    if args.check_config:
        print(
            json.dumps(
                {
                    "mensagem": "Configuracao do servidor do JARVIS validada com sucesso.",
                    "ambiente": config.build_environment_report(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    return run_server(config=config)


if __name__ == "__main__":
    raise SystemExit(main())
