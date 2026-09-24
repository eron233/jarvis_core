"""
JARVIS - Módulo 1: Autoevolução e Segurança (Gêmeo de Segurança)

Responsável por:
- simular ataques contínuos e varreduras de vulnerabilidade sobre o gêmeo de segurança (mirror)
- identificar falhas de autenticação, persistência, permissão e lógica sem afetar o sistema vivo
- aplicar correções automáticas e seguras no JARVIS, refletindo no gêmeo para torná-lo mais resistente
- reduzir progressivamente o escopo de vulnerabilidades disponíveis em ciclo contínuo
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from security.remediation_engine import RemediationEngine
from security.security_twin import SecurityTwin
from security.security_validation_engine import SecurityValidationEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVOLUTION_STATE_PATH = PROJECT_ROOT / "data" / "auto_evolution_state.json"


class AutoEvolutionEngine:
    """Motor de autoevolução contínua por análise e ataque simulado no Gêmeo de Segurança."""

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
        Executa um ciclo completo de autoevolução:
        1. Atualiza/sincroniza o gêmeo do sistema.
        2. Ataca e valida o gêmeo procurando falhas/vulnerabilidades.
        3. Identifica lacunas e gera plano de remediação.
        4. Aplica auto-correções seguras.
        5. Re-sincroniza o gêmeo, aumentando a resistência estrutural do sistema.
        """
        now = datetime.now(timezone.utc).isoformat()

        if runtime is None:
            from runtime.internal_agent_runtime import InternalAgentRuntime
            runtime = InternalAgentRuntime()
            runtime.bootstrap()

        # 1. Sincroniza estado do gêmeo
        self.twin.create_twin_snapshot(runtime=runtime)

        # 2. Executa bateria de testes e simulações defensivas no gêmeo
        validation_results = self.validator.run_all_validations()
        weaknesses = validation_results.get("fraquezas_detectadas", [])

        # 3. Gera plano de remediação
        remediation_plan = self.remediator.build_remediation_plan(weaknesses)

        # 4. Aplica correções seguras
        applied_actions = []
        if weaknesses:
            applied_actions = self.remediator.apply_safe_remediations(weaknesses)

        # 5. Atualiza o estado evolutivo do JARVIS
        evolution_report = {
            "ciclo_executado_em": now,
            "versao_gemeo": validation_results.get("twin_version"),
            "nivel_resistencia": "alto" if not weaknesses else ("medio" if len(weaknesses) <= 2 else "baixo"),
            "total_simulacoes_ataque": validation_results.get("total_scenarios", 0),
            "vulnerabilidades_encontradas": len(weaknesses),
            "vulnerabilidades_detalhes": weaknesses,
            "remediacoes_aplicadas": applied_actions,
            "status_evolucao": "resistencia_incrementada" if applied_actions else ("estavel" if not weaknesses else "pendente_aprovacao"),
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

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Persiste o estado de autoevolução em disco."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
