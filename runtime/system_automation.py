"""
JARVIS - Automação e Sensores do Sistema Operacional

Responsável por:
- lançamento seguro e supervisionado de aplicativos locais
- leitura de sensores de recursos do SO (CPU, Memória, Processos, Carga)
- interação com arquivos e diretórios autorizados do hospedeiro
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import subprocess
from typing import Any, Dict, List, Optional

# Comandos de sistema proibidos por segurança
FORBIDDEN_COMMANDS = {
    "rm -rf /", "format", "mkfs", "dd", "shutdown", "reboot", "del /f /s /q c:\\"
}

# Caracteres que encadeiam, redirecionam ou expandem comandos no shell.
# Uma lista de comandos proibidos so reconhece o que ja foi previsto; barrar os
# separadores impede que um comando autorizado carregue um segundo comando junto.
# Parenteses ficam de fora de proposito: aparecem em caminhos legitimos do
# Windows, como "C:\\Program Files (x86)".
SHELL_METACHARACTERS = ("&", "|", ";", "<", ">", "^", "$", "`", "\n", "\r", "\0")


class SystemAutomationEngine:
    """Motor de automação, execução controlada de apps e sensores do SO."""

    def __init__(self, allowed_work_dir: Optional[Path] = None) -> None:
        self.allowed_work_dir = Path(allowed_work_dir) if allowed_work_dir else Path.home()

    def launch_application(self, app_command: str) -> Dict[str, Any]:
        """
        Inicia um aplicativo ou comando local de forma supervisionada.
        """
        cmd_strip = app_command.strip().lower()
        if any(forbidden in cmd_strip for forbidden in FORBIDDEN_COMMANDS):
            return {
                "status": "bloqueado",
                "motivo": f"Comando '{app_command}' bloqueado pela política de segurança.",
            }

        encontrados = [caractere for caractere in SHELL_METACHARACTERS if caractere in app_command]
        if encontrados:
            return {
                "status": "bloqueado",
                "motivo": (
                    "Comando bloqueado: contém separador de shell "
                    f"({' '.join(repr(caractere) for caractere in encontrados)}), "
                    "que permitiria executar um segundo comando junto do aplicativo."
                ),
            }

        now = datetime.now(timezone.utc).isoformat()
        try:
            if platform.system() == "Windows":
                # Sem `shell=True`: com ele o Windows junta a lista numa unica linha
                # entregue ao interpretador, e qualquer separador dentro de
                # `app_command` viraria um comando novo. Sem ele, o argumento e
                # passado ja delimitado e o `cmd.exe` o trata como um valor unico.
                proc = subprocess.Popen(["cmd.exe", "/c", "start", "", app_command])
            elif platform.system() == "Darwin":
                proc = subprocess.Popen(["open", "-a", app_command])
            else:
                proc = subprocess.Popen(["xdg-open", app_command])

            return {
                "status": "sucesso",
                "comando": app_command,
                "pid_estimado": proc.pid,
                "lancado_em": now,
            }
        except Exception as e:
            return {"status": "erro", "motivo": str(e)}

    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Lê métricas reais e sensores de uso do hardware/SO hospedeiro.
        """
        load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)

        return {
            "sistema": platform.system(),
            "nos_rede": platform.node(),
            "cpus_logicos": os.cpu_count() or 1,
            "carga_media_1_5_15_min": list(load_avg),
            "pid_jarvis": os.getpid(),
        }

    def list_running_processes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Lista processos ativos no sistema operacional.
        """
        processes = []
        try:
            if platform.system() == "Windows":
                cmd = ["tasklist", "/FO", "CSV", "/NH"]
            else:
                cmd = ["ps", "-e", "-o", "pid,comm"]

            output = subprocess.check_output(cmd, text=True, timeout=5)
            lines = [line.strip() for line in output.splitlines() if line.strip()]

            for line in lines[:limit]:
                parts = line.split(",") if platform.system() == "Windows" else line.split(maxsplit=1)
                if parts:
                    processes.append({"raw_entry": line.replace('"', '')})
        except Exception:
            processes = [{"raw_entry": "jarvis_runtime (processo ativo)"}]

        return processes
