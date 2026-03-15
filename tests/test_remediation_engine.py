"""Testes unitarios para o motor de remediacao hibrida do JARVIS."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import SystemLoopConfig, bootstrap_runtime
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.system_config import JarvisEnvironmentConfig
from security.remediation_engine import RemediationEngine
from security.security_twin import SecurityTwin
from security.security_validation_engine import SecurityValidationEngine


def make_security_artifact_path(name: str, suffix: str) -> Path:
    """Retorna o path de artefato usado nos cenarios de remediacao."""

    return PROJECT_ROOT / "tests" / "_security_artifacts" / name / suffix


def reset_path(path: Path) -> None:
    """Limpa um artefato persistente antes da execucao do teste."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class RemediationEngineTests(unittest.TestCase):
    """Valida planejamento e autoaplicacao segura de remediacoes."""

    def build_context(self, name: str) -> tuple[InternalAgentRuntime, JarvisEnvironmentConfig, SecurityTwin, dict, dict, dict]:
        """Monta o contexto completo usado pelos cenarios de remediacao."""

        scenario_dir = make_security_artifact_path(name, "workspace")
        queue_path = scenario_dir / "data" / "task_queue_store.json"
        semantic_path = scenario_dir / "data" / "semantic_memory_store.json"
        goals_path = scenario_dir / "data" / "goals.json"
        twin_dir = scenario_dir / "twin_state"

        for path in (queue_path, semantic_path, goals_path, twin_dir / "latest_twin_snapshot.json"):
            reset_path(path)

        runtime, _ = bootstrap_runtime(
            runtime=InternalAgentRuntime(),
            config=SystemLoopConfig(
                queue_storage_path=queue_path,
                semantic_storage_path=semantic_path,
                goal_storage_path=goals_path,
                install_signal_handlers=False,
            ),
            logger=lambda _message: None,
        )

        goal = runtime.goal_manager.add_active_goal(
            title="Estabilizar autodefesa",
            description="Objetivo de remediacao segura",
            priority=9,
        )
        runtime.enqueue_task(
            {
                "task_id": f"remediate-{name}",
                "goal": "Revisar persistencia e auditoria",
                "description": "Correcao segura do estado interno",
                "domain": "runtime",
                "worker": "worker_runtime",
                "impact": 3,
                "urgency": 2,
                "parent_goal_id": goal["goal_id"],
            }
        )
        runtime.memory["semantic"].add_entry(
            content="Estado base para remediacao",
            domain="security",
            tags=["remediacao", "seguranca"],
            source="unit-test",
            importance=4,
            metadata={"contexto": "teste"},
        )

        config = JarvisEnvironmentConfig(
            env="production",
            api_host="0.0.0.0",
            api_port=8122,
            enable_runtime_loop=True,
            enable_dashboard=True,
            token="token-remediacao-segura",
            trusted_device_id="eron-celular-principal",
            data_dir=scenario_dir / "data",
            logs_dir=scenario_dir / "logs",
            reports_dir=scenario_dir / "reports",
            queue_storage_path=queue_path,
            semantic_storage_path=semantic_path,
            goals_storage_path=goals_path,
        )
        environment_report = config.build_environment_report()
        health_report = runtime.build_health_report(
            api_started_at="2026-03-13T00:00:00+00:00",
            token_configurado=True,
            dispositivo_confiavel_configurado=True,
        )
        twin = SecurityTwin(storage_dir=twin_dir)
        snapshot = twin.create_twin_snapshot(
            runtime=runtime,
            environment_report=environment_report,
            health_report=health_report,
            snapshot_name=f"remediation-{name}",
        )
        return runtime, config, twin, snapshot, environment_report, health_report

    def test_remediation_plan_builds_three_solutions_per_weakness(self) -> None:
        """Confirma que cada fraqueza gera tres solucoes estruturadas."""

        runtime, config, twin, snapshot, environment_report, health_report = self.build_context("solutions")
        validation_engine = SecurityValidationEngine()
        tampered_snapshot = deepcopy(snapshot)
        tampered_snapshot["configuration_snapshot"]["autenticacao_configurada"] = {
            "token_configurado": False,
            "dispositivo_confiavel_configurado": False,
        }
        tampered_snapshot["api_security_metadata"]["autenticacao_configurada"] = {
            "token_configurado": False,
            "dispositivo_confiavel_configurado": False,
        }
        tampered_snapshot["operational_state_snapshot"]["health_report"]["configuracao_minima_valida"] = False

        validation_report = validation_engine.run_validation_suite(twin_snapshot=tampered_snapshot)
        remediation_engine = RemediationEngine(twin=twin)
        remediation_plan = remediation_engine.build_remediation_plan(
            validation_report=validation_report,
            runtime=runtime,
            config=config,
            twin_snapshot=tampered_snapshot,
            environment_report=environment_report,
            health_report=health_report,
            auto_apply_safe=False,
        )

        self.assertGreaterEqual(remediation_plan["fraquezas_avaliadas"], 1)
        for plan in remediation_plan["planos_por_fraqueza"]:
            self.assertEqual(len(plan["solucoes"]), 3)
        auth_plan = next(
            plan for plan in remediation_plan["planos_por_fraqueza"] if plan["weakness_id"] == "auth_identity_guard_missing"
        )
        self.assertEqual(auth_plan["classificacao_correcao"], "correcao_assistida")

    def test_safe_persistence_remediation_is_auto_applied_and_audited(self) -> None:
        """Verifica autoaplicacao segura de remediacao e respectiva auditoria."""

        runtime, config, twin, snapshot, environment_report, health_report = self.build_context("auto_apply")
        validation_engine = SecurityValidationEngine()
        tampered_snapshot = deepcopy(snapshot)
        tampered_snapshot["operational_state_snapshot"]["memory_summary"]["integridade_basica"]["json_valido"] = False
        tampered_snapshot["operational_state_snapshot"]["memory_summary"]["integridade_basica"]["contagem_consistente"] = False
        tampered_snapshot["operational_state_snapshot"]["health_report"]["fila_carregada"] = False
        tampered_snapshot["operational_state_snapshot"]["health_report"]["ultima_persistencia_fila"] = None
        tampered_snapshot["operational_state_snapshot"]["health_report"]["ultima_persistencia_memoria"] = None
        tampered_snapshot["operational_state_snapshot"]["health_report"]["ultima_persistencia_objetivos"] = None

        validation_report = validation_engine.run_validation_suite(twin_snapshot=tampered_snapshot)
        remediation_engine = RemediationEngine(twin=twin)
        remediation_plan = remediation_engine.build_remediation_plan(
            validation_report=validation_report,
            runtime=runtime,
            config=config,
            twin_snapshot=tampered_snapshot,
            environment_report=environment_report,
            health_report=health_report,
            auto_apply_safe=True,
        )

        strategy_ids = {action["strategy_id"] for action in remediation_plan["acoes_automaticas_realizadas"]}
        audit_events = [entry["event"] for entry in runtime.audit_logger.entries]

        self.assertIn("refresh_runtime_persistence", strategy_ids)
        self.assertIn("security_remediation", audit_events)

    def test_authentication_gap_remains_pending_for_human_approval(self) -> None:
        """Garante que lacunas sensiveis de autenticacao fiquem pendentes de aprovacao."""

        runtime, config, twin, snapshot, environment_report, health_report = self.build_context("auth_pending")
        validation_engine = SecurityValidationEngine()
        tampered_snapshot = deepcopy(snapshot)
        tampered_snapshot["configuration_snapshot"]["autenticacao_configurada"] = {
            "token_configurado": False,
            "dispositivo_confiavel_configurado": False,
        }
        tampered_snapshot["api_security_metadata"]["autenticacao_configurada"] = {
            "token_configurado": False,
            "dispositivo_confiavel_configurado": False,
        }
        tampered_snapshot["operational_state_snapshot"]["health_report"]["configuracao_minima_valida"] = False

        validation_report = validation_engine.run_validation_suite(twin_snapshot=tampered_snapshot)
        remediation_engine = RemediationEngine(twin=twin)
        remediation_plan = remediation_engine.build_remediation_plan(
            validation_report=validation_report,
            runtime=runtime,
            config=config,
            twin_snapshot=tampered_snapshot,
            environment_report=environment_report,
            health_report=health_report,
            auto_apply_safe=True,
        )

        pending_ids = {item["weakness_id"] for item in remediation_plan["acoes_pendentes_de_aprovacao"]}
        automatic_ids = {item["weakness_id"] for item in remediation_plan["acoes_automaticas_realizadas"]}

        self.assertIn("auth_identity_guard_missing", pending_ids)
        self.assertNotIn("auth_identity_guard_missing", automatic_ids)


if __name__ == "__main__":
    unittest.main()
