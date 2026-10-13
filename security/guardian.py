"""JARVIS Guardian v0: observacao defensiva SOMENTE LEITURA do Microsoft Defender.

Nao e um antivírus independente. Nenhuma varredura, remocao, exclusao, alteracao
de preferencias, download ou quarentena e iniciada por este modulo.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
from typing import Any, Dict, Optional

# Scripts estaticos. NUNCA interpolar texto do usuario em comandos PowerShell.
_STATUS_SCRIPT = """
$ErrorActionPreference = 'Stop'
$data = Get-MpComputerStatus -ErrorAction Stop |
    Select-Object AMServiceEnabled, AntivirusEnabled, RealTimeProtectionEnabled,
        AntispywareEnabled, AntispywareSignatureLastUpdated, AMRunningMode,
        QuickScanEndTime, FullScanEndTime
if ($null -eq $data) { throw 'Defender nao retornou estado.' }
ConvertTo-Json -InputObject $data -Depth 4 -Compress
""".strip()

_DETECTIONS_SCRIPT = """
$ErrorActionPreference = 'Stop'
$items = @(Get-MpThreatDetection -ErrorAction Stop |
    Sort-Object InitialDetectionTime -Descending |
    Select-Object -First 30 ThreatID, InitialDetectionTime, ThreatStatusID,
        ActionSuccess, LastThreatStatusChangeTime)
ConvertTo-Json -InputObject $items -Depth 4 -Compress
""".strip()

_MAX_STDOUT = 96 * 1024
_TIMEOUT_SECONDS = 12
_ALLOWED_DETECTION_FIELDS = (
    "ThreatID", "InitialDetectionTime", "ThreatStatusID",
    "ActionSuccess", "LastThreatStatusChangeTime",
)


class Guardian:
    """Observa estado e historico do Defender sem promover deteccao a diagnostico."""

    def __init__(self, *, timeout_seconds: int = _TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = max(1, min(30, int(timeout_seconds)))

    @staticmethod
    def _failure(reason: str, category: str = "indisponivel") -> Dict[str, Any]:
        return {"status": category, "motivo": reason, "consultado": False}

    def _query(self, script: str) -> Dict[str, Any]:
        if platform.system() != "Windows":
            return self._failure("O backend do Microsoft Defender requer Windows.")
        # Powershell deve ser invocado pelo caminho absoluto do sistema, nunca
        # por 'powershell' resolvido no PATH de ferramentas de terceiros.
        system_root = Path(os.environ.get("SystemRoot") or "C:\\Windows")
        executable = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if not executable.is_file():
            return self._failure("Windows PowerShell nativo indisponivel.")

        env = {
            "SystemRoot": str(system_root),
            "windir": str(system_root),
            # Sem herdar tokens, chaves API nem variaveis JARVIS_*.
            "PATH": str(system_root / "System32") + os.pathsep + str(system_root),
        }
        argv = [
            str(executable), "-NoLogo", "-NoProfile", "-NonInteractive",
            "-Command", script,
        ]
        try:
            result = subprocess.run(
                argv, capture_output=True, timeout=self.timeout_seconds,
                env=env, check=False,
            )
        except subprocess.TimeoutExpired:
            return self._failure("A consulta ao Defender excedeu o tempo limite.", "timeout")
        except OSError:
            return self._failure("Nao foi possivel iniciar o PowerShell nativo.")

        if result.returncode != 0:
            # stderr frequentemente contem paths e detalhes locais; nao devolve-los
            # a endpoints e relatórios de acesso remoto.
            return self._failure("Defender indisponivel, permissao insuficiente ou cmdlet com erro.")
        if len(result.stdout) > _MAX_STDOUT:
            return self._failure("Defender retornou dados acima do limite configurado.", "erro_saida")
        try:
            payload = json.loads(result.stdout.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            return self._failure("Resposta do Defender nao e JSON valido.", "erro_saida")
        return {"status": "consultado", "consultado": True, "dados": payload}

    def observe(self) -> Dict[str, Any]:
        """Faz leitura pontual, sem agendar servico nem iniciar scanner."""
        observed_at = datetime.now(timezone.utc).isoformat()
        status_query = self._query(_STATUS_SCRIPT)
        detections_query = self._query(_DETECTIONS_SCRIPT)

        config: Optional[Dict[str, Any]] = None
        if status_query["consultado"] and isinstance(status_query["dados"], dict):
            raw = status_query["dados"]
            config = {
                "servico_ativo": raw.get("AMServiceEnabled") if isinstance(raw.get("AMServiceEnabled"), bool) else None,
                "antivirus_ativo": raw.get("AntivirusEnabled") if isinstance(raw.get("AntivirusEnabled"), bool) else None,
                "tempo_real_ativo": raw.get("RealTimeProtectionEnabled") if isinstance(raw.get("RealTimeProtectionEnabled"), bool) else None,
                "modo_execucao": raw.get("AMRunningMode"),
                "atualizacao_assinaturas": raw.get("AntispywareSignatureLastUpdated"),
                "ultima_verificacao_rapida": raw.get("QuickScanEndTime"),
                "ultima_verificacao_completa": raw.get("FullScanEndTime"),
            }

        events: Optional[list[Dict[str, Any]]] = None
        if detections_query["consultado"] and isinstance(detections_query["dados"], list):
            events = []
            for item in detections_query["dados"][:30]:
                if isinstance(item, dict):
                    events.append({key: item.get(key) for key in _ALLOWED_DETECTION_FIELDS})
        elif detections_query["consultado"]:
            detections_query = self._failure(
                "Historico de deteccoes nao retornou lista JSON valida.", "erro_saida"
            )

        valid_state = config is not None
        valid_events = events is not None
        complete = valid_state and valid_events
        overall = "consultado" if complete else (
            "parcial" if valid_state or valid_events else "indisponivel"
        )
        return {
            "status": overall,
            "consultado_em": observed_at,
            "plataforma": platform.system(),
            "origem": "Microsoft Defender Antivirus (cmdlets locais oficiais)",
            "leitura_apenas": True,
            "verificacao_antivirus_iniciada": False,
            "ameacas_ativas_confirmadas": None,
            "maquina_livre_de_malware_confirmada": False,
            "protecao": config,
            "deteccoes_historicas": events,
            "total_eventos_retornados": len(events) if events is not None else None,
            "consultas": {
                "estado": {k: v for k, v in status_query.items() if k != "dados"},
                "historico": {k: v for k, v in detections_query.items() if k != "dados"},
            },
            "aviso": (
                "Eventos sao historicos e podem ja ter sido resolvidos. "
                "Sem eventos nao prova ausencia de malware; nenhum arquivo foi analisado."
            ),
        }
