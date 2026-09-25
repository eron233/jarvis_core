"""
JARVIS - Motor de Tomada de Decisão JEV (Joint Executive Vector)

Responsável por:
- projetar decisões em um espaço vetorial de utilidade executiva
- combinar o Vetor de Estado do Sistema (S), Vetor de Objetivos (G), Avaliador de Políticas (P) e Função de Utilidade/Poda (U)
- eliminar impulsividade, adulação e respostas subjetivas não fundamentadas
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JEV_DIR = PROJECT_ROOT / "data" / "jev_decisions"


class JEVDecisionEngine:
    """Motor de decisão executiva multicritério baseado no conceito JEV (Joint Executive Vector)."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_JEV_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_decision_vector(
        self,
        decision_context: str,
        options: List[Dict[str, Any]],
        system_state_vector: Optional[Dict[str, Any]] = None,
        goal_vector: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Avalia as opções de decisão projetando os vetores S, G, P e U, colapsando na decisão ótima.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Vetor de Estado do Sistema (S)
        s_vector = system_state_vector or {
            "recursos_hardware": "ok",
            "restricoes_seguranca": "ativas",
            "autonomia_nivel": "supervisionada",
        }

        # 2. Vetor de Intenções e Objetivos (G)
        g_vector = goal_vector or {
            "meta_principal": decision_context,
            "prioridade_peso": 1.0,
            "foco_verdade_objetiva": True,
        }

        # 3. Avaliador de Políticas e Função de Utilidade/Poda (P & U)
        evaluated_options = []
        for option in options:
            opt_name = option.get("nome", "Opção")
            utility_score = float(option.get("utilidade_0_10", 5.0))
            risk_score = float(option.get("risco_0_10", 2.0))
            cost_score = float(option.get("custo_0_10", 1.0))

            # Função de Recompensa Executiva JEV: J = Utility - (Risk * 1.5) - (Cost * 0.5)
            jev_value = utility_score - (risk_score * 1.5) - (cost_score * 0.5)

            # Poda de opções com risco excessivo ou retorno negativo
            pruned = jev_value < 0 or risk_score > 8.0

            evaluated_options.append({
                "opcao": opt_name,
                "detalhes": option,
                "jev_vector_score": round(jev_value, 2),
                "poda_status": "podada" if pruned else "valida",
                "motivo_poda": "Risco excessivo ou utilidade líquida negativa" if pruned else None,
            })

        # 4. Seleção da Decisão Ótima Colapsada
        valid_options = [o for o in evaluated_options if o["poda_status"] == "valida"]
        if not valid_options:
            valid_options = evaluated_options

        best_decision = max(valid_options, key=lambda o: o["jev_vector_score"])

        decision_report = {
            "contexto_decisao": decision_context,
            "avaliado_em": now,
            "vetor_estado_sistema": s_vector,
            "vetor_objetivos": g_vector,
            "total_opcoes_avaliadas": len(options),
            "opcoes_validadas": valid_options,
            "decisao_otima_colapsada": best_decision,
            "justificativa_jev_ptbr": (
                f"Decisão Executiva JEV: Selecionada a opção '{best_decision['opcao']}' "
                f"com Score Vetorial de {best_decision['jev_vector_score']}. "
                "Decisão objetiva, imune a adulação ou impulsividade."
            ),
        }

        self._save_jev_record(decision_report)
        return decision_report

    def _save_jev_record(self, record: Dict[str, Any]) -> None:
        """Salva o registro da decisão JEV em disco."""
        file_id = f"jev_decision_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path = self.data_dir / file_id
        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
