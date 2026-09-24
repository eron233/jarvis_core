"""
JARVIS - Motor de Relatorio Semanal de Seguranca (Bloco 12.6)

Responsavel por:
- consolidar fraquezas, remediacoes, acoes automaticas e excecoes operacionais
- separar novidades recentes de achados recorrentes
- gerar relatorio semanal em pt-BR e salvar em disco/JSON para API e Dashboard

Integracoes principais:
- security.self_defense
- security.threat_model_engine
- security.remediation_engine
- executive_planner.audit
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "weekly_security_report_latest.json"


class WeeklySecurityReportEngine:
    """Consolidador de relatorio semanal de seguranca em pt-BR."""

    def __init__(self, report_path: Optional[Path] = None) -> None:
        self.report_path = Path(report_path) if report_path else DEFAULT_REPORT_PATH

    def generate_report(
        self,
        self_defense_report: Optional[Dict[str, Any]] = None,
        threat_model: Optional[Dict[str, Any]] = None,
        remediation_summary: Optional[Dict[str, Any]] = None,
        audit_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Gera e persiste o relatorio semanal consolidado de seguranca.
        """
        now = datetime.now(timezone.utc).isoformat()

        sd_data = self_defense_report or {}
        tm_data = threat_model or {}
        rem_data = remediation_summary or {}
        events = audit_events or []

        weaknesses = sd_data.get("fraquezas_detectadas", [])
        automatic_actions = sd_data.get("acoes_automaticas_aplicadas", [])
        risk_level = sd_data.get("nivel_risco_geral", "baixo")

        # Classifica achados recorrentes vs novos
        critical_risks = []
        recurring_findings = []
        new_findings = []

        for w in weaknesses:
            w_item = {
                "id": w.get("id"),
                "titulo": w.get("titulo", w.get("id")),
                "dominio": w.get("dominio"),
                "severidade": w.get("severidade", "medio"),
                "descricao": w.get("descricao", ""),
                "remediado": w.get("remediado", False),
            }
            if w.get("severidade") in ("alto", "critico"):
                critical_risks.append(w_item)
            if w.get("recorrente", False):
                recurring_findings.append(w_item)
            else:
                new_findings.append(w_item)

        total_audited = len(events)
        security_exceptions = [e for e in events if e.get("event") in ("auth_failure", "replay_blocked", "security_alert")]

        summary_ptbr = (
            f"Relatorio Semanal de Seguranca JARVIS - Risco Geral: {risk_level.upper()}. "
            f"Total de fraquezas detectadas: {len(weaknesses)} ({len(critical_risks)} criticas/altas). "
            f"Acoes de remediacao automaticas aplicadas: {len(automatic_actions)}. "
            f"Eventos de excecao registrados na auditoria: {len(security_exceptions)}."
        )

        report_payload = {
            "periodo": "Semanal",
            "gerado_em": now,
            "nivel_risco_geral": risk_level,
            "resumo_ptbr": summary_ptbr,
            "estatisticas": {
                "total_fraquezas": len(weaknesses),
                "riscos_criticos_ou_altos": len(critical_risks),
                "novos_achados": len(new_findings),
                "achados_recorrentes": len(recurring_findings),
                "acoes_automaticas_aplicadas": len(automatic_actions),
                "excecoes_de_seguranca_auditadas": len(security_exceptions),
            },
            "riscos_criticos": critical_risks,
            "novos_achados": new_findings,
            "achados_recorrentes": recurring_findings,
            "acoes_automaticas": automatic_actions,
            "excecoes_operacionais": security_exceptions[:10], # top 10 recentes
            "modelo_ameacas_resumo": {
                "ativos_protegidos": len(tm_data.get("ativos_protegidos", [])),
                "superficies_contato": len(tm_data.get("superficies_contato", [])),
            },
        }

        self._save_report_atomic(report_payload)
        return report_payload

    def load_latest_report(self) -> Optional[Dict[str, Any]]:
        """Carrega o ultimo relatorio semanal do disco."""
        if not self.report_path.exists():
            return None
        try:
            return json.loads(self.report_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_report_atomic(self, payload: Dict[str, Any]) -> None:
        """Salva o relatorio atomicamente em disco."""
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.report_path.with_name(f"{self.report_path.name}.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, self.report_path)
