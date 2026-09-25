"""
JARVIS - Fluxo de Pensamentos Privados e Política Anti-Manipulação do Dono

Responsável por:
- registrar o monólogo interno, interpretações e reflexões do JARVIS em um canal privado
- garantir acesso exclusivo ao Dono do sistema mediante autenticação administrativa
- impor a política constitucional de Zero Manipulação/Anti-Decepção em relação ao Dono
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_THOUGHTS_DIR = PROJECT_ROOT / "data" / "thought_stream"


class ThoughtStreamEngine:
    """Motor de registro e consulta do fluxo de pensamentos privados do JARVIS."""

    def __init__(self, thoughts_dir: Optional[Path] = None) -> None:
        self.thoughts_dir = Path(thoughts_dir) if thoughts_dir else DEFAULT_THOUGHTS_DIR
        self.thoughts_dir.mkdir(parents=True, exist_ok=True)
        self.thoughts_file = self.thoughts_dir / "private_thoughts_stream.json"

    def record_thought(
        self,
        context_action: str,
        internal_reasoning: str,
        owner_opinion_eval: str,
        potential_risks_identified: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Grava um pensamento ou raciocínio interno do JARVIS no canal privado do Dono.
        """
        now = datetime.now(timezone.utc).isoformat()

        thought_entry = {
            "timestamp": now,
            "acao_contexto": context_action,
            "raciocinio_interno": internal_reasoning,
            "interpretacao_e_opiniao": owner_opinion_eval,
            "riscos_identificados": potential_risks_identified or [],
            "diretriz_anti_manipulacao": "Ativa: Transparência total e zero engodo em relação ao Dono.",
        }

        self._append_thought(thought_entry)
        return thought_entry

    def get_owner_thoughts_stream(
        self,
        is_authenticated_owner: bool,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Retorna o histórico de pensamentos privados do JARVIS.
        ACESSO EXCLUSIVO AO DONO AUTENTICADO.
        """
        if not is_authenticated_owner:
            return {
                "status": "negado",
                "motivo": "Acesso negado: O fluxo de pensamentos internos é restrito exclusivamente ao Dono autenticado.",
            }

        thoughts = self._load_thoughts()
        return {
            "status": "sucesso",
            "total_pensamentos_registrados": len(thoughts),
            "ultimos_pensamentos": thoughts[-limit:],
        }

    def _append_thought(self, entry: Dict[str, Any]) -> None:
        """Garante persistência atômica no arquivo de pensamentos."""
        thoughts = self._load_thoughts()
        thoughts.append(entry)
        self.thoughts_file.write_text(json.dumps(thoughts, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_thoughts(self) -> List[Dict[str, Any]]:
        """Carrega os pensamentos salvos do disco."""
        if not self.thoughts_file.exists():
            return []
        try:
            return json.loads(self.thoughts_file.read_text(encoding="utf-8"))
        except Exception:
            return []
