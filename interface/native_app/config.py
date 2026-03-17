"""Configuracao compartilhada do aplicativo nativo do JARVIS."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys

from runtime.system_config import (
    JarvisEnvironmentConfig,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_runtime_python_executable() -> Path:
    """Resolve um interpretador adequado para subir o runtime em subprocesso."""

    configured = os.environ.get("PYTHON_BIN")
    if configured:
        return Path(configured)

    executable = Path(sys.executable)
    pythonw_name = executable.name.lower()
    if pythonw_name == "pythonw.exe":
        python_candidate = executable.with_name("python.exe")
        if python_candidate.exists():
            return python_candidate
    return executable


@dataclass(frozen=True)
class NativeAppConfig:
    """Agrupa endpoints, autenticacao e temporizadores do app nativo."""

    api_base_url: str
    api_token: str
    device_id: str
    python_executable: Path
    project_root: Path
    runtime_entrypoint: Path
    startup_timeout_seconds: float
    startup_poll_interval_seconds: float
    request_timeout_seconds: float
    status_refresh_interval_ms: int
    brain_refresh_interval_ms: int
    health_path: str = "/health"

    @classmethod
    def from_env(cls) -> "NativeAppConfig":
        """Carrega a configuracao principal a partir do ambiente atual."""

        runtime_config = JarvisEnvironmentConfig.from_env()
        api_port = int(os.environ.get("JARVIS_API_PORT", runtime_config.api_port))
        api_base_url = os.environ.get(
            "JARVIS_NATIVE_API_BASE_URL",
            f"http://127.0.0.1:{api_port}",
        ).rstrip("/")
        return cls(
            api_base_url=api_base_url,
            api_token=runtime_config.token,
            device_id=runtime_config.trusted_device_id,
            python_executable=resolve_runtime_python_executable(),
            project_root=PROJECT_ROOT,
            runtime_entrypoint=PROJECT_ROOT / "runtime" / "server.py",
            startup_timeout_seconds=float(os.environ.get("JARVIS_NATIVE_STARTUP_TIMEOUT", "35")),
            startup_poll_interval_seconds=float(os.environ.get("JARVIS_NATIVE_STARTUP_POLL", "0.75")),
            request_timeout_seconds=float(os.environ.get("JARVIS_NATIVE_REQUEST_TIMEOUT", "10")),
            status_refresh_interval_ms=int(os.environ.get("JARVIS_NATIVE_STATUS_REFRESH_MS", "15000")),
            brain_refresh_interval_ms=int(os.environ.get("JARVIS_NATIVE_BRAIN_REFRESH_MS", "20000")),
        )
