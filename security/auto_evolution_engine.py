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
import logging
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

from security.remediation_engine import RemediationEngine
from security.security_twin import SecurityTwin
from security.security_validation_engine import SecurityValidationEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVOLUTION_STATE_PATH = PROJECT_ROOT / "data" / "auto_evolution_state.json"

LOGGER = logging.getLogger("jarvis.security.auto_evolution")


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
        checkpoint = self._create_state_checkpoint()

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
                rollback_executed = self._rollback_to_checkpoint(checkpoint)

        evolution_report = {
            "ciclo_executado_em": now,
            "checkpoint_tag": checkpoint["tag"],
            "checkpoint_commit": checkpoint["commit"],
            "checkpoint_disponivel": checkpoint["disponivel"],
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

    def _create_state_checkpoint(self) -> Dict[str, Any]:
        """
        Registra o estado da arvore de trabalho antes de qualquer alteracao.

        Retorno:
        - dicionario com a etiqueta, o commit do checkpoint quando existe,
          se a arvore ja estava limpa e se o checkpoint pode ser usado.

        Efeitos no sistema:
        - nenhum na arvore de trabalho; `git stash create` apenas monta um commit
          solto com o estado atual e devolve o identificador dele.

        O identificador precisa ser guardado: `git stash create` nao registra o
        commit em lugar nenhum, entao descartar a saida equivale a nao ter
        checkpoint algum.
        """

        tag = f"auto_evolution_checkpoint_{int(datetime.now(timezone.utc).timestamp())}"
        try:
            resultado = subprocess.run(
                ["git", "stash", "create", tag],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return {"tag": tag, "commit": None, "arvore_limpa": False, "disponivel": False}

        if resultado.returncode != 0:
            return {"tag": tag, "commit": None, "arvore_limpa": False, "disponivel": False}

        commit = resultado.stdout.strip()
        if not commit:
            # Sem saida, a arvore ja estava limpa: qualquer alteracao presente
            # depois deste ponto foi produzida pelo proprio ciclo de evolucao.
            return {"tag": tag, "commit": None, "arvore_limpa": True, "disponivel": True}

        return {"tag": tag, "commit": commit, "arvore_limpa": False, "disponivel": True}

    def _rollback_to_checkpoint(self, checkpoint: Dict[str, Any]) -> bool:
        """
        Desfaz as alteracoes do ciclo restaurando o estado registrado.

        Parametros:
        - checkpoint: descricao devolvida por `_create_state_checkpoint`.

        Retorno:
        - `True` quando a restauracao foi executada.

        Efeitos no sistema:
        - restaura os arquivos versionados ao estado do checkpoint.

        Sem checkpoint utilizavel nada e revertido. A versao anterior executava
        `git checkout -- .` de forma incondicional, o que descartava tambem
        qualquer trabalho nao commitado do dono que nada tinha a ver com o ciclo.
        """

        if not checkpoint.get("disponivel"):
            LOGGER.warning(
                "[auto_evolution] rollback recusado: nenhum checkpoint utilizavel foi registrado."
            )
            return False

        commit = checkpoint.get("commit")
        comando = ["git", "checkout", commit, "--", "."] if commit else ["git", "checkout", "--", "."]

        try:
            resultado = subprocess.run(
                comando,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            return resultado.returncode == 0
        except Exception:
            return False

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Persiste o estado de autoevolução em disco."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
