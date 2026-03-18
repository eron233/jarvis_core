"""
JARVIS - Servico Leve do Windows

Responsavel por:
- iniciar automaticamente o servidor do Jarvis no startup do Windows
- monitorar o processo principal do runtime
- reiniciar o processo quando ele morrer inesperadamente

Integracoes principais:
- runtime.server
- runtime.system_config
- main

Observacao:
- este servico supervisiona o entrypoint oficial de servidor, sem criar um bootstrap paralelo
"""

from __future__ import annotations

from pathlib import Path
import os
import site
import subprocess
import sys
from typing import Sequence

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
except ImportError:  # pragma: no cover - protegido para ambientes sem pywin32
    servicemanager = None
    win32event = None
    win32service = None
    win32serviceutil = None


# JARVIS_RUNTIME_ENTRYPOINT
# ==================================================
# BLOCO: Definicao do servico e monitoramento do processo
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERVICE_PYTHON = Path(r"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe")
SERVICE_LOG_PATH = PROJECT_ROOT / "logs" / "jarvis.log"
SERVICE_NAME = "JarvisRuntimeService"
SERVICE_DISPLAY_NAME = "Jarvis Runtime Service"
SERVICE_DESCRIPTION = "Mantem o runtime, a API local e o painel do Jarvis ativos no Windows."


def resolve_python_executable() -> Path:
    """Resolve o interpretador Python do servico."""

    configured = os.environ.get("JARVIS_SERVICE_PYTHON")
    if configured:
        return Path(configured)
    if DEFAULT_SERVICE_PYTHON.exists():
        return DEFAULT_SERVICE_PYTHON
    return Path(sys.executable)


def resolve_python_service_host() -> Path | None:
    """Resolve o executavel `pythonservice.exe` do pywin32 sem depender de copia em Program Files."""

    configured = os.environ.get("JARVIS_SERVICE_HOST_EXE")
    if configured:
        candidate = Path(configured)
        if candidate.exists():
            return candidate

    candidates = [
        Path(sys.executable).with_name("pythonservice.exe"),
        Path(site.getusersitepackages()) / "win32" / "pythonservice.exe",
    ]
    for site_dir in site.getsitepackages():
        candidates.append(Path(site_dir) / "win32" / "pythonservice.exe")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_runtime_command(
    python_executable: Path | None = None,
    project_root: Path | None = None,
) -> list[str]:
    """Monta o comando oficial do processo monitorado pelo servico."""

    resolved_python = Path(python_executable or resolve_python_executable())
    root = Path(project_root or PROJECT_ROOT)
    return [str(resolved_python), str(root / "runtime" / "server.py")]


def _append_service_log(message: str) -> None:
    """Registra mensagens do servico no log central do Jarvis."""

    SERVICE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SERVICE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


if win32serviceutil is not None:

    class JarvisWindowsService(win32serviceutil.ServiceFramework):
        """Servico Windows que supervisiona o servidor principal do Jarvis."""

        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION
        _exe_name_ = str(resolve_python_service_host()) if resolve_python_service_host() is not None else None

        def __init__(self, args) -> None:
            """Inicializa a instancia e prepara o estado interno do componente."""
            super().__init__(args)
            self.h_wait_stop = win32event.CreateEvent(None, 0, 0, None)
            self.process: subprocess.Popen[str] | None = None
            self.project_root = PROJECT_ROOT
            self.command = build_runtime_command()

        def SvcStop(self) -> None:
            """Solicita a parada do servico e encerra o processo monitorado."""

            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._log("Encerramento do servico solicitado.")
            win32event.SetEvent(self.h_wait_stop)
            self._stop_runtime_process()

        def SvcDoRun(self) -> None:
            """Mantem o processo principal do Jarvis vivo enquanto o servico estiver ativo."""

            self._log("Servico do Jarvis iniciado.")
            if servicemanager is not None:
                servicemanager.LogInfoMsg("JarvisWindowsService iniciado.")

            while True:
                wait_result = win32event.WaitForSingleObject(self.h_wait_stop, 2000)
                if wait_result == win32event.WAIT_OBJECT_0:
                    break

                if self.process is None:
                    self._start_runtime_process()
                    continue

                return_code = self.process.poll()
                if return_code is None:
                    continue

                self._log(f"Runtime do Jarvis encerrou com codigo {return_code}. Reiniciando.")
                self._start_runtime_process()

            self._stop_runtime_process()
            self._log("Servico do Jarvis encerrado.")

        def _start_runtime_process(self) -> None:
            """Executa a rotina interna de start runtime process."""
            self._stop_runtime_process()
            env = dict(os.environ)
            env.setdefault("PYTHONUNBUFFERED", "1")
            self._log("Subindo processo principal do Jarvis.")
            self.process = subprocess.Popen(
                self.command,
                cwd=str(self.project_root),
                env=env,
            )

        def _stop_runtime_process(self) -> None:
            """Executa a rotina interna de stop runtime process."""
            if self.process is None:
                return
            if self.process.poll() is None:
                self._log("Encerrando processo principal do Jarvis.")
                self.process.terminate()
                try:
                    self.process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    self._log("Processo do Jarvis nao encerrou a tempo. Forcando kill.")
                    self.process.kill()
                    self.process.wait(timeout=10)
            self.process = None

        def _log(self, message: str) -> None:
            """Executa a rotina interna de log."""
            _append_service_log(message)
            if servicemanager is not None:
                servicemanager.LogInfoMsg(message)


def main(argv: Sequence[str] | None = None) -> int:
    """Encaminha comandos de instalacao/start do servico para o pywin32."""

    if win32serviceutil is None:
        print("pywin32 nao esta disponivel. Instale a dependencia antes de usar o servico do Windows.")
        return 2

    if argv is not None:
        sys.argv = [sys.argv[0], *list(argv)]

    win32serviceutil.HandleCommandLine(JarvisWindowsService)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
