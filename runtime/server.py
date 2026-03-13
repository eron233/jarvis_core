"""Runner de servidor para deploy simples do JARVIS em VPS."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from threading import Thread
from typing import Any, Dict, Optional

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
        self.logger = logger
        self.loop = JarvisSystemLoop(
            runtime=runtime,
            config=config,
            logger=self._log,
        )
        self.thread: Thread | None = None
        self.last_summary: Dict[str, Any] | None = None

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            return

        self.thread = Thread(
            target=self._run_loop,
            name="jarvis-runtime-loop",
            daemon=True,
        )
        self.thread.start()

    def stop(self, reason: str = "requested", join_timeout: float = 30.0) -> Dict[str, Any] | None:
        if self.thread is None:
            return self.last_summary

        self.loop.request_shutdown(reason)
        self.thread.join(join_timeout)

        if self.thread.is_alive():
            self.logger.warning("[shutdown] loop continuo ainda nao encerrou apos %.1f segundo(s).", join_timeout)

        return deepcopy(self.last_summary)

    def _run_loop(self) -> None:
        self.last_summary = self.loop.run()

    def _log(self, message: str) -> None:
        self.logger.info(message)


class JarvisServerContext:
    """Contexto de execucao do servidor do JARVIS."""

    def __init__(
        self,
        config: JarvisEnvironmentConfig,
        runtime: InternalAgentRuntime | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
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
            goal_storage_path=self.config.goals_storage_path,
        )

    def _write_report(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _utc_now() -> str:
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


def main() -> int:
    """Ponto de entrada do servidor para deploy em VPS simples."""

    try:
        config = JarvisEnvironmentConfig.from_env()
    except ValueError as exc:
        print(str(exc))
        return 2

    return run_server(config=config)


if __name__ == "__main__":
    raise SystemExit(main())
