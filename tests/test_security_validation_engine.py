"""Testes unitarios para a validacao interna controlada do JARVIS."""

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
from security.security_twin import SecurityTwin
from security.security_validation_engine import SecurityValidationEngine


def make_security_artifact_path(name: str, suffix: str) -> Path:
    return PROJECT_ROOT / "tests" / "_security_artifacts" / name / suffix


def reset_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class SecurityValidationEngineTests(unittest.TestCase):
    def build_snapshot(self, name: str) -> dict:
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
            title="Manter integridade interna",
            description="Objetivo de seguranca controlada",
            priority=8,
        )
        runtime.enqueue_task(
            {
                "task_id": f"validate-{name}",
                "goal": "Revisar trilha interna",
                "description": "Confirmar consistencia do sistema",
                "domain": "runtime",
                "worker": "worker_runtime",
                "impact": 3,
                "urgency": 2,
                "parent_goal_id": goal["goal_id"],
            }
        )
        runtime.memory["semantic"].add_entry(
            content="Memoria sanitizada para validacao interna",
            domain="security",
            tags=["validacao", "seguranca"],
            source="unit-test",
            importance=4,
            metadata={"topico": "integridade"},
        )

        environment_report = JarvisEnvironmentConfig(
            env="production",
            api_host="0.0.0.0",
            api_port=8121,
            enable_runtime_loop=True,
            enable_dashboard=True,
            token="token-validacao-segura",
            trusted_device_id="eron-celular-principal",
            data_dir=scenario_dir / "data",
            logs_dir=scenario_dir / "logs",
            reports_dir=scenario_dir / "reports",
            queue_storage_path=queue_path,
            semantic_storage_path=semantic_path,
            goals_storage_path=goals_path,
        ).build_environment_report()
        health_report = runtime.build_health_report(
            api_started_at="2026-03-13T00:00:00+00:00",
            token_configurado=True,
            dispositivo_confiavel_configurado=True,
        )

        twin = SecurityTwin(storage_dir=twin_dir)
        return twin.create_twin_snapshot(
            runtime=runtime,
            environment_report=environment_report,
            health_report=health_report,
            snapshot_name=f"validation-{name}",
        )

    def test_validation_suite_passes_on_healthy_twin(self) -> None:
        snapshot = self.build_snapshot("healthy")
        engine = SecurityValidationEngine()

        report = engine.run_validation_suite(twin_snapshot=snapshot)

        self.assertEqual(
            report["mensagem"],
            "Validacao interna controlada concluida apenas sobre o gemeo autorizado.",
        )
        self.assertTrue(report["integridade_do_gemeo"]["valido"])
        self.assertEqual(report["resumo"]["total_cenarios"], 6)
        self.assertEqual(report["resumo"]["total_fraquezas"], 0)
        self.assertTrue(
            all(result["status"] == "aprovado" for result in report["resultados_de_cenario"])
        )

    def test_validation_suite_detects_auth_and_operational_integrity_gaps(self) -> None:
        snapshot = self.build_snapshot("auth_gap")
        engine = SecurityValidationEngine()
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
        tampered_snapshot["operational_state_snapshot"]["planner_summary"]["acoplado"] = False
        tampered_snapshot["task_queue_snapshot"]["tasks"][0]["parent_goal_id"] = "goal-inexistente"

        report = engine.run_validation_suite(twin_snapshot=tampered_snapshot)
        weakness_ids = {weakness["weakness_id"] for weakness in report["fraquezas"]}

        self.assertIn("auth_identity_guard_missing", weakness_ids)
        self.assertIn("configuration_startup_degraded", weakness_ids)
        self.assertIn("operational_integrity_gap", weakness_ids)
        self.assertGreaterEqual(report["resumo"]["total_fraquezas"], 3)

    def test_validation_suite_detects_persistence_and_continuity_gaps(self) -> None:
        snapshot = self.build_snapshot("persistence_gap")
        engine = SecurityValidationEngine()
        tampered_snapshot = deepcopy(snapshot)

        tampered_snapshot["operational_state_snapshot"]["memory_summary"]["integridade_basica"]["json_valido"] = False
        tampered_snapshot["operational_state_snapshot"]["memory_summary"]["integridade_basica"]["contagem_consistente"] = False
        tampered_snapshot["operational_state_snapshot"]["health_report"]["fila_carregada"] = False
        tampered_snapshot["operational_state_snapshot"]["health_report"]["ultima_persistencia_fila"] = None
        tampered_snapshot["operational_state_snapshot"]["health_report"]["ultima_persistencia_memoria"] = None
        tampered_snapshot["operational_state_snapshot"]["health_report"]["ultima_persistencia_objetivos"] = None

        report = engine.run_validation_suite(twin_snapshot=tampered_snapshot)
        weakness_ids = {weakness["weakness_id"] for weakness in report["fraquezas"]}

        self.assertIn("persistence_inconsistency", weakness_ids)
        self.assertIn("continuity_degraded", weakness_ids)
        self.assertEqual(report["integridade_do_gemeo"]["valido"], True)


if __name__ == "__main__":
    unittest.main()
