"""
JARVIS - Autoaperfeicoamento Estrutural

Responsavel por:
- registrar aprendizados internos do proprio sistema
- consolidar sugestoes de melhoria estrutural
- preparar a arquitetura para evolucao futura sem alterar o runtime atual

Integracoes principais:
- runtime.internal_agent_runtime
- security.self_defense
- FULL_STRUCTURAL_ANALYSIS_REPORT_PTBR.md
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List


# JARVIS_CORE_COMPONENT
# ==================================================
# BLOCO: Registro leve de aprendizado futuro
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORAGE_PATH = PROJECT_ROOT / "data" / "self_improvement_knowledge.json"


@dataclass
class SelfImprovementAdvisor:
    """Mantem observacoes internas e sugestoes de evolucao estrutural do Jarvis."""

    storage_path: Path = field(default_factory=lambda: DEFAULT_STORAGE_PATH)
    learnings: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.storage_path = Path(self.storage_path)
        self.load_snapshot()

    def register_learning(
        self,
        observation: str,
        source: str = "runtime",
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Registra um aprendizado interno do sistema."""

        learning = {
            "id": f"learning-{len(self.learnings) + 1}",
            "observation": str(observation).strip(),
            "source": source,
            "metadata": deepcopy(metadata or {}),
            "created_at": self._utc_now(),
        }
        self.learnings.append(learning)
        self.snapshot()
        return deepcopy(learning)

    def suggest_structural_improvements(
        self,
        runtime_state: Dict[str, Any] | None = None,
        analysis_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Gera sugestoes leves de melhoria a partir do estado atual conhecido."""

        runtime_state = runtime_state or {}
        analysis_report = analysis_report or {}
        suggestions = [
            "Consolidar relatorios periodicos de seguranca em um painel historico.",
            "Aprofundar heuristicas reutilizaveis da memoria procedural por dominio.",
            "Expandir os workers apenas em tarefas cognitivas seguras e auditaveis.",
        ]

        if runtime_state.get("queue_depth", 0) > 5:
            suggestions.insert(0, "Melhorar politicas de fila para evitar acumulacao operacional.")

        if analysis_report.get("resumo", {}).get("fraquezas_detectadas", 0) > 0:
            suggestions.insert(0, "Priorizar fortalecimento defensivo antes de ampliar autonomia.")

        return {
            "mensagem": "Sugestoes estruturais futuras geradas com sucesso.",
            "total_aprendizados": len(self.learnings),
            "sugestoes_priorizadas": suggestions[:5],
        }

    def snapshot(self) -> Dict[str, Any]:
        """Persiste o estado atual do conhecimento adquirido."""

        payload = {
            "updated_at": self._utc_now(),
            "learning_count": len(self.learnings),
            "learnings": deepcopy(self.learnings),
        }
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return payload

    def load_snapshot(self) -> Dict[str, Any]:
        """Recarrega o armazenamento local de aprendizado."""

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.learnings = []
            return {
                "updated_at": self._utc_now(),
                "learning_count": 0,
                "learnings": [],
            }

        payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        self.learnings = [deepcopy(item) for item in payload.get("learnings", [])]
        return payload

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
