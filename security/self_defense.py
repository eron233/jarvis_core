"""
JARVIS - Autodefesa Operacional

Responsavel por:
- executar auditorias internas autorizadas de seguranca
- consolidar modelo de ameaca, gemeo isolado, validacao e remediacao segura
- produzir relatorios operacionais de autodiagnostico do sistema

Integracoes principais:
- runtime.internal_agent_runtime
- security.threat_model_engine
- security.security_twin
- security.security_validation_engine
- security.remediation_engine
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
from typing import Any, Dict, List

from security.remediation_engine import RemediationEngine
from security.security_knowledge_core import SecurityKnowledgeCore
from security.security_twin import SecurityTwin
from security.security_validation_engine import SecurityValidationEngine
from security.threat_model_engine import ThreatModelEngine


# JARVIS_SECURITY_GATE
# ==================================================
# BLOCO: Auditoria defensiva autorizada e isolada
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "self_defense_latest.json"


@dataclass
class SelfDefenseMonitor:
    """Orquestra o autodiagnostico defensivo do Jarvis em ambiente autorizado."""

    knowledge_core: SecurityKnowledgeCore = field(default_factory=SecurityKnowledgeCore)
    threat_model_engine: ThreatModelEngine = field(default_factory=ThreatModelEngine)
    security_twin: SecurityTwin = field(default_factory=SecurityTwin)
    validation_engine: SecurityValidationEngine = field(default_factory=SecurityValidationEngine)
    remediation_engine: RemediationEngine = field(default_factory=RemediationEngine)
    report_path: Path = field(default_factory=lambda: DEFAULT_REPORT_PATH)

    def __post_init__(self) -> None:
        self.report_path = Path(self.report_path)

    def run_periodic_audit(
        self,
        runtime: Any,
        environment_report: Dict[str, Any] | None = None,
        health_report: Dict[str, Any] | None = None,
        auto_apply_safe: bool = True,
    ) -> Dict[str, Any]:
        """Executa o ciclo completo de autodefesa sobre o estado autorizado do proprio Jarvis."""

        runtime.bootstrap()
        runtime_state = deepcopy(runtime.describe_state())
        effective_environment = deepcopy(environment_report or {})
        effective_health = deepcopy(
            health_report
            or runtime.build_health_report(
                api_started_at=runtime.started_at,
                token_configurado=bool(
                    effective_environment.get("autenticacao_configurada", {}).get("token_configurado")
                ),
                dispositivo_confiavel_configurado=bool(
                    effective_environment.get("autenticacao_configurada", {}).get(
                        "dispositivo_confiavel_configurado"
                    )
                ),
            )
        )

        threat_model = self.threat_model_engine.build_threat_model(
            runtime_state=runtime_state,
            health_report=effective_health,
            environment_report=effective_environment,
        )
        twin_snapshot = self.security_twin.create_twin_snapshot(
            runtime=runtime,
            environment_report=effective_environment,
            health_report=effective_health,
            snapshot_name="security-self-defense",
        )
        twin_summary = self.security_twin.describe_twin_state(twin_snapshot)
        validation_report = self.validation_engine.run_validation_suite(twin_snapshot=twin_snapshot)
        remediation_report = self.remediation_engine.build_remediation_plan(
            validation_report=validation_report,
            runtime=runtime,
            config=None,
            twin_snapshot=twin_snapshot,
            environment_report=effective_environment,
            health_report=effective_health,
            auto_apply_safe=auto_apply_safe,
        )
        port_report = self._build_port_report(effective_environment)
        configuration_findings = self._build_configuration_findings(
            environment_report=effective_environment,
            health_report=effective_health,
        )

        report = {
            "mensagem": "Autodiagnostico defensivo do JARVIS executado em ambiente autorizado.",
            "executado_em": self._utc_now(),
            "somente_ambiente_autorizado": True,
            "correcoes_seguras_automaticas_ativas": bool(auto_apply_safe),
            "estado_runtime": runtime_state,
            "conhecimento_defensivo": {
                "dominios": self.knowledge_core.list_domains(),
                "snapshot": self.knowledge_core.build_knowledge_snapshot(),
            },
            "modelo_ameaca": threat_model,
            "gemeo_de_seguranca": twin_summary,
            "validacao_controlada": validation_report,
            "remediacao": remediation_report,
            "portas_observadas": port_report,
            "possiveis_falhas_de_configuracao": configuration_findings,
            "resumo": {
                "risco_geral": threat_model["resumo_ptbr"]["risco_geral"],
                "fraquezas_detectadas": validation_report["resumo"]["total_fraquezas"],
                "acoes_automaticas_realizadas": len(
                    remediation_report["acoes_automaticas_realizadas"]
                ),
                "acoes_pendentes_de_aprovacao": len(
                    remediation_report["acoes_pendentes_de_aprovacao"]
                ),
                "portas_ativas_observadas": len(
                    [port for port in port_report["portas"] if port["escutando_localmente"]]
                ),
            },
        }
        self._persist_report(report)
        return report

    def _build_port_report(self, environment_report: Dict[str, Any]) -> Dict[str, Any]:
        host = str(environment_report.get("host_api") or "127.0.0.1")
        port = int(environment_report.get("porta_api") or 0)
        ports: List[Dict[str, Any]] = []
        if port > 0:
            ports.append(
                {
                    "host": host,
                    "porta": port,
                    "bind_publico": host in {"0.0.0.0", "::"},
                    "escutando_localmente": self._probe_local_port(port),
                }
            )

        return {
            "mensagem": "Estado observado das portas locais relacionadas ao Jarvis.",
            "portas": ports,
        }

    def _build_configuration_findings(
        self,
        environment_report: Dict[str, Any],
        health_report: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        auth_report = environment_report.get("autenticacao_configurada", {})

        if not auth_report.get("token_configurado", False):
            findings.append(
                {
                    "tipo": "segredo_padrao",
                    "mensagem": "Token administrativo ainda nao foi customizado.",
                    "gravidade": "alto",
                }
            )
        if not auth_report.get("dispositivo_confiavel_configurado", False):
            findings.append(
                {
                    "tipo": "device_trust_incompleto",
                    "mensagem": "Dispositivo confiavel principal ainda nao foi explicitamente configurado.",
                    "gravidade": "alto",
                }
            )
        if str(environment_report.get("host_api") or "") in {"0.0.0.0", "::"}:
            findings.append(
                {
                    "tipo": "bind_amplo",
                    "mensagem": "API exposta em bind amplo. Garanta firewall e rede confiavel.",
                    "gravidade": "medio",
                }
            )
        if not health_report.get("configuracao_minima_valida", False):
            findings.append(
                {
                    "tipo": "configuracao_minima_invalida",
                    "mensagem": "Healthcheck indica configuracao minima incompleta para operacao segura.",
                    "gravidade": "alto",
                }
            )
        return findings

    def _persist_report(self, report: Dict[str, Any]) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _probe_local_port(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            return False

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
