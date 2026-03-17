"""Testes dos orgaos vitais internos de estabilidade do runtime."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import SystemLoopConfig, bootstrap_runtime
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.vital_organs.structural_integrity_monitor import StructuralIntegrityMonitor


class VitalOrgansTests(unittest.TestCase):
    """Valida acoplamento silencioso e utilidade basica dos orgaos vitais."""

    def build_config(self, root: Path, enable_background: bool = False) -> SystemLoopConfig:
        """Monta uma configuracao isolada para exercitar os orgaos vitais."""

        data_dir = root / "data"
        reports_dir = root / "reports"
        return SystemLoopConfig(
            cycle_sleep_seconds=0.1,
            idle_sleep_seconds=0.1,
            install_signal_handlers=False,
            queue_storage_path=data_dir / "task_queue_store.json",
            semantic_storage_path=data_dir / "semantic_memory_store.json",
            procedural_storage_path=data_dir / "procedural_memory_store.json",
            goal_storage_path=data_dir / "goals.json",
            cognitive_evolution_storage_path=data_dir / "cognitive_evolution_history.json",
            audit_storage_path=data_dir / "runtime_audit_store.json",
            device_registry_path=data_dir / "device_registry.json",
            self_defense_report_path=reports_dir / "self_defense_latest.json",
            enable_vital_organs_background=enable_background,
        )

    def test_bootstrap_configures_vital_organs_sem_expor_interface(self) -> None:
        """Garante configuracao interna sem expor os orgaos vitais na API publica do runtime."""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, _state = bootstrap_runtime(
                runtime=InternalAgentRuntime(),
                config=self.build_config(Path(temp_dir), enable_background=False),
            )

            self.assertIsNotNone(runtime.vital_organs_orchestrator)
            report = runtime.run_vital_organs_cycle_once()

            self.assertIsNotNone(report)
            self.assertEqual(report["summary"]["orgaos_ativos"], 5)
            self.assertNotIn("vital_organs", runtime.describe_state())
            self.assertNotIn("vital_organs", runtime.build_system_report())
            self.assertTrue(runtime.vital_organs_orchestrator.report_path.exists())

    def test_bootstrap_real_starta_background_dos_orgaos_vitais(self) -> None:
        """Confirma que o boot real ativa os orgaos vitais automaticamente."""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, _state = bootstrap_runtime(
                runtime=InternalAgentRuntime(),
                config=self.build_config(Path(temp_dir), enable_background=True),
            )

            orchestrator = runtime.vital_organs_orchestrator
            self.assertIsNotNone(orchestrator)
            self.assertTrue(orchestrator.snapshot() is not None)
            self.assertTrue(orchestrator.report_path.exists())
            self.assertTrue(orchestrator._thread is not None and orchestrator._thread.is_alive())

            runtime.shutdown_vital_organs(reason="test_cleanup")
            self.assertFalse(orchestrator._thread is not None and orchestrator._thread.is_alive())

    def test_structural_integrity_monitor_detects_legacy_store(self) -> None:
        """Garante detecao explicita de stores legados ainda presentes."""

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            official_path = root / "data" / "task_queue_store.json"
            legacy_path = root / "executive_planner" / "task_queue_store.json"
            official_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            official_path.write_text('{"task_count": 0, "tasks": []}', encoding="utf-8")
            legacy_path.write_text('{"task_count": 1, "tasks": []}', encoding="utf-8")

            class _RuntimeStub:
                @staticmethod
                def _utc_now() -> str:
                    return "2026-03-16T00:00:00+00:00"

                @staticmethod
                def describe_state() -> dict[str, str]:
                    return {
                        "queue_store": str(official_path),
                        "semantic_store": str(root / "data" / "semantic_memory_store.json"),
                        "procedural_store": str(root / "data" / "procedural_memory_store.json"),
                        "goal_store": str(root / "data" / "goals.json"),
                        "device_registry_store": str(root / "data" / "device_registry.json"),
                        "audit_store": str(root / "data" / "runtime_audit_store.json"),
                        "cognitive_evolution_store": str(root / "data" / "cognitive_evolution_history.json"),
                        "self_defense_report_path": str(root / "reports" / "self_defense_latest.json"),
                    }

            monitor = StructuralIntegrityMonitor(
                project_root=root,
                official_paths={
                    "queue_storage_path": official_path,
                    "semantic_storage_path": root / "data" / "semantic_memory_store.json",
                    "procedural_storage_path": root / "data" / "procedural_memory_store.json",
                    "goals_storage_path": root / "data" / "goals.json",
                    "device_registry_path": root / "data" / "device_registry.json",
                    "audit_storage_path": root / "data" / "runtime_audit_store.json",
                    "cognitive_evolution_storage_path": root / "data" / "cognitive_evolution_history.json",
                    "self_defense_report_path": root / "reports" / "self_defense_latest.json",
                },
                legacy_paths={"queue_storage_path": legacy_path},
            )

            report = monitor.run(_RuntimeStub())

            self.assertEqual(report["status"], "atencao")
            self.assertTrue(
                any(item["kind"] == "legacy_store_present" for item in report["violacoes"])
            )


if __name__ == "__main__":
    unittest.main()
