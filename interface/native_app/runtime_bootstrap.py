"""Bootstrap do runtime local para o app nativo do JARVIS."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import time
from typing import Callable

from interface.native_app.api_client import ApiClientError, JarvisApiClient
from interface.native_app.config import NativeAppConfig


class RuntimeBootstrapError(RuntimeError):
    """Erro ao garantir o runtime disponivel para o app."""


@dataclass(frozen=True)
class RuntimeBootstrapResult:
    """Resume como o runtime ficou disponivel para a interface nativa."""

    health_payload: dict
    started_runtime: bool
    runtime_pid: int | None
    startup_duration_seconds: float


class JarvisRuntimeBootstrapper:
    """Detecta um runtime existente ou sobe um novo processo oculto."""

    def __init__(self, config: NativeAppConfig, api_client: JarvisApiClient) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        self.config = config
        self.api_client = api_client
        self._last_process: subprocess.Popen[str] | None = None

    def ensure_runtime_available(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> RuntimeBootstrapResult:
        """Garante que a API local esteja saudavel antes de abrir a janela principal."""

        started_at = time.monotonic()
        self._emit(progress_callback, "Verificando runtime local...")
        health_payload = self.probe_health()
        if health_payload is not None:
            self._emit(progress_callback, "Runtime ja estava ativo.")
            return RuntimeBootstrapResult(
                health_payload=health_payload,
                started_runtime=False,
                runtime_pid=None,
                startup_duration_seconds=time.monotonic() - started_at,
            )

        self._emit(progress_callback, "Runtime indisponivel. Iniciando processo oculto...")
        process = self.start_runtime_process()
        self._emit(progress_callback, "Aguardando healthcheck positivo...")
        ready_payload = self.wait_until_ready(process=process, progress_callback=progress_callback)
        return RuntimeBootstrapResult(
            health_payload=ready_payload,
            started_runtime=True,
            runtime_pid=process.pid,
            startup_duration_seconds=time.monotonic() - started_at,
        )

    def probe_health(self) -> dict | None:
        """Consulta o healthcheck publico sem subir outra instancia desnecessaria."""

        try:
            payload = self.api_client.public_healthcheck()
        except ApiClientError:
            return None
        if payload.get("mensagem"):
            return payload
        return None

    def start_runtime_process(self) -> subprocess.Popen[str]:
        """Sobe o servidor oficial do Jarvis sem expor uma janela de console ao usuario."""

        stdout_path = self.config.project_root / "logs" / "native_app_runtime_stdout.log"
        stderr_path = self.config.project_root / "logs" / "native_app_runtime_stderr.log"
        stdout_path.parent.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        env.setdefault("PYTHONUNBUFFERED", "1")
        env.setdefault("JARVIS_ENABLE_DASHBOARD", "0")

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        command = [
            str(self.config.python_executable),
            str(self.config.runtime_entrypoint),
        ]

        stdout_handle = stdout_path.open("a", encoding="utf-8")
        stderr_handle = stderr_path.open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.config.project_root),
                env=env,
                stdout=stdout_handle,
                stderr=stderr_handle,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        finally:
            stdout_handle.close()
            stderr_handle.close()

        self._last_process = process
        return process

    def wait_until_ready(
        self,
        *,
        process: subprocess.Popen[str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict:
        """Espera o healthcheck responder sem bloquear indefinidamente."""

        deadline = time.monotonic() + self.config.startup_timeout_seconds
        while time.monotonic() < deadline:
            payload = self.probe_health()
            if payload is not None:
                self._emit(progress_callback, "Runtime disponivel. Abrindo interface nativa...")
                return payload

            if process is not None and process.poll() is not None:
                stderr_tail = self._tail_file(self.config.project_root / "logs" / "native_app_runtime_stderr.log")
                raise RuntimeBootstrapError(
                    "O runtime encerrou antes do healthcheck ficar positivo.\n"
                    f"Ultimas linhas do log:\n{stderr_tail}"
                )

            time.sleep(self.config.startup_poll_interval_seconds)

        raise RuntimeBootstrapError(
            "Tempo excedido aguardando o runtime ficar disponivel no healthcheck local."
        )

    @staticmethod
    def _tail_file(path: Path, line_count: int = 30) -> str:
        """Retorna as ultimas linhas do arquivo de log informado."""

        if not path.exists():
            return "Log ainda nao criado."
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-line_count:]) or "Log vazio."

    @staticmethod
    def _emit(callback: Callable[[str], None] | None, message: str) -> None:
        """Encaminha progresso textual para a UI sem acoplamento adicional."""

        if callback is not None:
            callback(message)

