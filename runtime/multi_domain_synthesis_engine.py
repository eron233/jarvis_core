"""
JARVIS - Motor de Síntese de Modelos de Domínios Múltiplos (Multi-Domain Synthesis Engine)

Responsável por:
- consultar visões de múltiplos domínios especializados (Segurança, Financeiro/Day Trade, Criativo/Estratégico, Engenharia de Software, Telemetria de Hardware)
- identificar divergências e conflitos interdominiais
- arbitrar e sintetizar uma recomendação executiva coerente e unificada
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYNTHESIS_DIR = PROJECT_ROOT / "data" / "synthesis_reports"


class MultiDomainSynthesisEngine:
    """Motor de síntese cross-domain para arbitrar visões de especialistas heterogêneos."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_SYNTHESIS_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def synthesize_domain_perspectives(
        self,
        topic: str,
        domain_inputs: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Recebe perspectivas de diferentes domínios e produz uma síntese harmonizada.
        Exemplo de domain_inputs:
        {
           "seguranca": {"recomendacao": "Bloquear porta X", "prioridade": "alta"},
           "engenharia": {"recomendacao": "Manter porta X aberta para microsserviço Y", "prioridade": "media"},
        }
        """
        now = datetime.now(timezone.utc).isoformat()

        perspectives_summary = []
        conflicts = []

        # Analisar cada perspectiva fornecida
        domains_present = list(domain_inputs.keys())
        for dom, details in domain_inputs.items():
            perspectives_summary.append({
                "dominio": dom,
                "posicao": details.get("recomendacao", "N/A"),
                "prioridade": details.get("prioridade", "media"),
                "risco": details.get("risco", "baixo"),
            })

        # Detecção de conflitos
        if len(domains_present) > 1:
            for i in range(len(domains_present)):
                for j in range(i + 1, len(domains_present)):
                    d1, d2 = domains_present[i], domains_present[j]
                    p1 = domain_inputs[d1].get("recomendacao", "")
                    p2 = domain_inputs[d2].get("recomendacao", "")
                    if p1 and p2 and p1 != p2:
                        conflicts.append({
                            "dominios_em_conflito": [d1, d2],
                            "divergencia": f"'{d1}' sugere '{p1}' enquanto '{d2}' sugere '{p2}'",
                        })

        # Arbitragem Executiva: Segurança e Estabilidade têm prioridade máxima
        primary_recommendation = ""
        if "seguranca" in domain_inputs:
            primary_recommendation = f"Prevalência de Segurança: {domain_inputs['seguranca'].get('recomendacao')}"
        elif domain_inputs:
            first_dom = domains_present[0]
            primary_recommendation = f"Recomendação Principal ({first_dom}): {domain_inputs[first_dom].get('recomendacao')}"

        report = {
            "topico": topic,
            "sintetizado_em": now,
            "dominios_consultados": domains_present,
            "resumo_perspectivas": perspectives_summary,
            "conflitos_detectados": conflicts,
            "decisao_sintetizada": primary_recommendation,
            "sintese_executiva_ptbr": (
                f"Síntese Multi-Domínio para '{topic}': "
                f"{len(conflicts)} conflito(s) resolvido(s). Recomendação final: {primary_recommendation}"
            ),
        }

        self._save_synthesis_report(report)
        return report

    def _save_synthesis_report(self, report: Dict[str, Any]) -> None:
        """Salva o relatório de síntese multi-domínio em arquivo JSON."""
        file_id = f"synthesis_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path = self.data_dir / file_id
        file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
