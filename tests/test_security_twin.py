"""Testes unitarios para o gemeo de seguranca do JARVIS."""

from copy import deepcopy
import json
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


def make_security_artifact_path(name: str, suffix: str) -> Path:
    return PROJECT_ROOT / "tests" / "_security_artifacts" / name / suffix


def reset_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class SecurityTwinTests(unittest.TestCase):
    def build_runtime_and_reports(self, name: str) -> tuple[InternalAgentRuntime, dict, dict, SecurityTwin]:
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
            title="Fortalecer seguranca interna",
            description="Objetivo reservado para reduzir risco operacional",
            priority=9,
        )
        runtime.enqueue_task(
            {
                "task_id": f"secure-{name}",
                "goal": "Revisar configuracao sensivel do sistema",
                "description": "Mapear risco operacional confidencial",
                "domain": "runtime",
                "worker": "worker_runtime",
                "impact": 4,
                "urgency": 3,
                "risk": 2,
                "parent_goal_id": goal["goal_id"],
                "evidence": ["evidencia interna confidencial"],
            }
        )
        runtime.memory["semantic"].add_entry(
            content="Segredo operacional interno do Jarvis",
            domain="security",
            tags=["segredo", "seguranca"],
            source="unit-test",
            importance=5,
            metadata={"credencial": "super-secreta", "origem": "laboratorio"},
        )

        config = JarvisEnvironmentConfig(
            env="production",
            api_host="0.0.0.0",
            api_port=8120,
            enable_runtime_loop=True,
            enable_dashboard=True,
            token="token-super-seguro",
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
        return runtime, environment_report, health_report, twin

    def test_create_and_load_twin_snapshot_with_sanitization(self) -> None:
        runtime, environment_report, health_report, twin = self.build_runtime_and_reports("create")

        snapshot = twin.create_twin_snapshot(
            runtime=runtime,
            environment_report=environment_report,
            health_report=health_report,
            snapshot_name="twin-create",
        )
        loaded = twin.load_twin_snapshot(snapshot["persistencia"]["snapshot_path"])
        serialized = json.dumps(loaded, ensure_ascii=False, sort_keys=True)

        self.assertTrue(Path(snapshot["persistencia"]["snapshot_path"]).exists())
        self.assertTrue(twin.latest_snapshot_path.exists())
        self.assertTrue(loaded["isolated"])
        self.assertEqual(loaded["task_queue_snapshot"]["task_count"], 1)
        self.assertEqual(loaded["goal_snapshot"]["active_goal_count"], 1)
        self.assertGreaterEqual(loaded["semantic_memory_snapshot"]["entry_count"], 1)
        self.assertNotIn("Mapear risco operacional confidencial", serialized)
        self.assertNotIn("Fortalecer seguranca interna", serialized)
        self.assertNotIn("Segredo operacional interno do Jarvis", serialized)
        self.assertEqual(
            loaded["api_security_metadata"]["autenticacao_configurada"]["token_configurado"],
            True,
        )

    def test_describe_twin_state_reports_summary_in_ptbr(self) -> None:
        runtime, environment_report, health_report, twin = self.build_runtime_and_reports("describe")

        snapshot = twin.create_twin_snapshot(
            runtime=runtime,
            environment_report=environment_report,
            health_report=health_report,
            snapshot_name="twin-describe",
        )
        description = twin.describe_twin_state(snapshot)

        self.assertEqual(
            description["mensagem"],
            "Gemeo de seguranca pronto para validacao interna controlada.",
        )
        self.assertTrue(description["isolado"])
        self.assertEqual(description["tarefas_espelhadas"], 1)
        self.assertEqual(description["objetivos_ativos_espelhados"], 1)
        self.assertIn(description["risco_geral"], {"baixo", "medio", "alto", "critico"})

    def test_validate_twin_integrity_detects_tampering(self) -> None:
        runtime, environment_report, health_report, twin = self.build_runtime_and_reports("validate")

        snapshot = twin.create_twin_snapshot(
            runtime=runtime,
            environment_report=environment_report,
            health_report=health_report,
            snapshot_name="twin-validate",
        )
        valid_report = twin.validate_twin_integrity(
            snapshot,
            forbidden_values=[
                "Mapear risco operacional confidencial",
                "Fortalecer seguranca interna",
                "Segredo operacional interno do Jarvis",
            ],
        )
        tampered_snapshot = deepcopy(snapshot)
        tampered_snapshot["task_queue_snapshot"]["task_count"] = 9
        tampered_snapshot["sanitizacao"]["segredos_omitidos"] = False
        tampered_report = twin.validate_twin_integrity(tampered_snapshot)

        self.assertTrue(valid_report["valido"])
        self.assertFalse(tampered_report["valido"])
        self.assertIn("fila_consistente", tampered_report["problemas"])
        self.assertIn("sanitizacao_configurada", tampered_report["problemas"])


if __name__ == "__main__":
    unittest.main()
