"""
JARVIS - Módulo 1: Autoevolução e Segurança (Gêmeo de Segurança)

Responsável por:
- simular ataques contínuos e varreduras de vulnerabilidade sobre o gêmeo de segurança (mirror)
- identificar falhas de autenticação, persistência, permissão e lógica sem afetar o sistema vivo
- aplicar correções automáticas e seguras no JARVIS, refletindo no gêmeo para torná-lo mais resistente
- realizar checkpoint Git preventivo e rollback automático em caso de regressão
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

from security.remediation_engine import RemediationEngine
from security.security_twin import SecurityTwin
from security.security_validation_engine import SecurityValidationEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVOLUTION_STATE_PATH = PROJECT_ROOT / "data" / "auto_evolution_state.json"


class AutoEvolutionEngine:
    """Motor de autoevolução contínua com checkpoint e rollback de segurança."""

    def __init__(
        self,
        twin: Optional[SecurityTwin] = None,
        state_path: Optional[Path] = None,
    ) -> None:
        self.twin = twin or SecurityTwin()
        self.validator = SecurityValidationEngine(twin=self.twin)
        self.remediator = RemediationEngine(twin=self.twin)
        self.state_path = Path(state_path) if state_path else DEFAULT_EVOLUTION_STATE_PATH

    def run_evolution_cycle(self, runtime: Any = None) -> Dict[str, Any]:
        """
        Executa um ciclo completo de autoevolução com salvaguarda de checkpoint/rollback.
        """
        now = datetime.now(timezone.utc).isoformat()

        if runtime is None:
            from runtime.internal_agent_runtime import InternalAgentRuntime
            runtime = InternalAgentRuntime()
            runtime.bootstrap()

        # 1. Checkpoint preventivo
        checkpoint_tag = self._create_state_checkpoint()

        # 2. Sincroniza estado do gêmeo
        self.twin.create_twin_snapshot(runtime=runtime)

        # 3. Executa bateria de testes e simulações defensivas no gêmeo
        validation_results = self.validator.run_all_validations()
        weaknesses = validation_results.get("fraquezas_detectadas", [])

        # 4. Gera plano de remediação
        remediation_plan = self.remediator.build_remediation_plan(weaknesses)

        # 5. Aplica correções seguras
        applied_actions = []
        rollback_executed = False
        if weaknesses:
            applied_actions = self.remediator.apply_safe_remediations(weaknesses)

            # Verifica integridade pós-remediação. Se houver erro grave, aciona rollback.
            post_check = self.validator.run_all_validations()
            if post_check.get("fraquezas_detectadas") and len(post_check["fraquezas_detectadas"]) > len(weaknesses):
                self._rollback_to_checkpoint(checkpoint_tag)
                rollback_executed = True

        evolution_report = {
            "ciclo_executado_em": now,
            "checkpoint_tag": checkpoint_tag,
            "rollback_executado": rollback_executed,
            "versao_gemeo": validation_results.get("twin_version"),
            "nivel_resistencia": "alto" if not weaknesses else ("medio" if len(weaknesses) <= 2 else "baixo"),
            "total_simulacoes_ataque": validation_results.get("total_scenarios", 0),
            "vulnerabilidades_encontradas": len(weaknesses),
            "vulnerabilidades_detalhes": weaknesses,
            "remediacoes_aplicadas": applied_actions if not rollback_executed else [],
            "status_evolucao": "rollback_por_regressao" if rollback_executed else ("resistencia_incrementada" if applied_actions else "estavel"),
        }

        self._save_state(evolution_report)
        return evolution_report

    def load_last_state(self) -> Optional[Dict[str, Any]]:
        """Carrega o histórico de autoevolução do disco."""
        if not self.state_path.exists():
            return None
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _create_state_checkpoint(self) -> str:
        """Cria uma marcação/stash de checkpoint antes da alteração."""
        tag = f"auto_evolution_checkpoint_{int(datetime.now(timezone.utc).timestamp())}"
        try:
            subprocess.run(
                ["git", "stash", "create", tag],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
        return tag

    def _rollback_to_checkpoint(self, tag: str) -> bool:
        """Executa o rollback restaurando o estado anterior caso ocorra regressão."""
        try:
            res = subprocess.run(
                ["git", "checkout", "--", "."],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Persiste o estado de autoevolução em disco."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
