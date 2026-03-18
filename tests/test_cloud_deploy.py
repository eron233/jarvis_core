"""Testes unitarios para a preparacao do JARVIS para nuvem."""

from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.queue import TaskQueue
from intent_layer.goal_manager import GoalManager
from main import SystemLoopConfig, bootstrap_runtime
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.server import JarvisServerContext
from runtime.system_config import JarvisEnvironmentConfig


def make_cloud_artifact_path(name: str, suffix: str) -> Path:
    """Retorna um path isolado para artefatos de nuvem simulada."""

    return PROJECT_ROOT / "tests" / "_cloud_artifacts" / name / suffix


def reset_path(path: Path) -> None:
    """Recria o ponto de partida limpo de um arquivo de teste."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class CloudPreparationTests(unittest.TestCase):
    """Valida configuracao, recuperacao e contexto de servidor para deploy."""

    def test_environment_config_loads_defaults(self) -> None:
        """Confirma que a configuracao padrao carrega stores oficiais e bootstrap seguro."""

        scenario_root = make_cloud_artifact_path("defaults", "workspace")
        if scenario_root.exists():
            shutil.rmtree(scenario_root)

        config = JarvisEnvironmentConfig.from_env(environ={}, project_root=scenario_root)

        self.assertEqual(config.env, "development")
        self.assertEqual(config.api_host, "0.0.0.0")
        self.assertEqual(config.api_port, 8000)
        self.assertTrue(config.enable_runtime_loop)
        self.assertTrue(config.enable_dashboard)
        self.assertEqual(config.queue_storage_path, scenario_root / "data" / "task_queue_store.json")
        self.assertEqual(config.semantic_storage_path, scenario_root / "data" / "semantic_memory_store.json")
        self.assertEqual(config.procedural_storage_path, scenario_root / "data" / "procedural_memory_store.json")
        self.assertEqual(config.goals_storage_path, scenario_root / "data" / "goals.json")
        self.assertFalse(config.token == "jarvis-local-dev-token")
        self.assertFalse(config.trusted_device_id == "jarvis-dispositivo-local")
        self.assertFalse(config.enable_simple_web_login)
        self.assertTrue(config.access_bootstrap_path.exists())
        self.assertTrue(config.admin_bootstrap_report_path.exists())

    def test_environment_config_habilita_login_web_simples_por_env(self) -> None:
        """Confirma a leitura explicita da flag de recuperacao web."""

        config = JarvisEnvironmentConfig.from_env(
            environ={
                "JARVIS_ADMIN_PASSWORD": "senha-web-segura-2026",
                "JARVIS_SIMPLE_WEB_LOGIN": "true",
            },
            project_root=PROJECT_ROOT,
        )

        self.assertTrue(config.enable_simple_web_login)

    def test_environment_config_rejects_weak_admin_password_from_env(self) -> None:
        """Garante que a credencial admin legada nao seja mais aceita como valor efetivo."""

        with self.assertRaises(ValueError) as context:
            JarvisEnvironmentConfig.from_env(
                environ={"JARVIS_ADMIN_PASSWORD": "alter ego"},
                project_root=PROJECT_ROOT,
            )

        self.assertIn("JARVIS_ADMIN_PASSWORD", str(context.exception))

    def test_bootstrap_runtime_recovers_corrupted_storage(self) -> None:
        """Verifica recuperacao segura quando os arquivos persistidos estao corrompidos."""

        scenario_dir = make_cloud_artifact_path("corrupted_recovery", "data")
        queue_path = scenario_dir / "task_queue_store.json"
        semantic_path = scenario_dir / "semantic_memory_store.json"
        goals_path = scenario_dir / "goals.json"

        for path in (queue_path, semantic_path, goals_path):
            reset_path(path)
            path.write_text("{arquivo-corrompido", encoding="utf-8")

        logs: list[str] = []
        runtime, state = bootstrap_runtime(
            runtime=InternalAgentRuntime(),
            config=SystemLoopConfig(
                queue_storage_path=queue_path,
                semantic_storage_path=semantic_path,
                goal_storage_path=goals_path,
                install_signal_handlers=False,
            ),
            logger=logs.append,
        )

        self.assertEqual(state["status"], "initialized")
        self.assertTrue(queue_path.exists())
        self.assertTrue(semantic_path.exists())
        self.assertTrue(goals_path.exists())
        self.assertTrue(any("corrompida" in message or "corrompidos" in message for message in logs))
        self.assertGreaterEqual(len(list(queue_path.parent.glob("*.corrompido-*.json"))), 3)
        self.assertEqual(runtime.describe_state()["queue_store"], str(queue_path))
        self.assertEqual(runtime.describe_state()["goal_store"], str(goals_path))
        self.assertEqual(runtime.describe_state()["semantic_store"], str(semantic_path))

    def test_server_context_bootstraps_paths_and_exposes_health(self) -> None:
        """Valida bootstrap do contexto de servidor e exposicao dos endpoints principais."""

        scenario_dir = make_cloud_artifact_path("server_context", "workspace")
        data_dir = scenario_dir / "data"
        logs_dir = scenario_dir / "logs"
        reports_dir = scenario_dir / "reports"
        queue_path = data_dir / "task_queue_store.json"
        semantic_path = data_dir / "semantic_memory_store.json"
        goals_path = data_dir / "goals.json"
        device_registry_path = data_dir / "device_registry.json"
        self_defense_report_path = reports_dir / "self_defense_latest.json"

        for path in (queue_path, semantic_path, goals_path, device_registry_path, self_defense_report_path):
            reset_path(path)

        queue = TaskQueue(storage_path=queue_path)
        queue.enqueue(
            {
                "task_id": "deploy-1",
                "goal": "Validar bootstrap em VPS",
                "description": "Confirmar recarga de fila",
                "domain": "runtime",
                "worker": "worker_runtime",
                "impact": 2,
                "urgency": 1,
            }
        )
        queue.save_to_disk()

        semantic_memory = SemanticMemory(storage_path=semantic_path)
        semantic_memory.add_entry(
            content="Memoria persistida para deploy",
            domain="system",
            tags=["deploy", "bootstrap"],
            source="unit-test",
            importance=4,
            metadata={"tipo": "bootstrap"},
        )
        semantic_memory.snapshot()

        goal_manager = GoalManager(storage_path=goals_path)
        goal_manager.add_active_goal(
            title="Subir JARVIS em VPS",
            description="Objetivo ativo de deploy",
            priority=8,
        )

        config = JarvisEnvironmentConfig(
            env="production",
            api_host="0.0.0.0",
            api_port=8111,
            enable_runtime_loop=False,
            enable_dashboard=True,
            token="token-deploy-seguro",
            trusted_device_id="eron-celular-principal",
            data_dir=data_dir,
            logs_dir=logs_dir,
            reports_dir=reports_dir,
            queue_storage_path=queue_path,
            semantic_storage_path=semantic_path,
            goals_storage_path=goals_path,
            device_registry_path=device_registry_path,
            self_defense_report_path=self_defense_report_path,
        )
        with patch.dict(
            "os.environ",
            {
                "JARVIS_ADMIN_PASSWORD": "senha-deploy-segura-2026",
                "JARVIS_TOKEN": "token-deploy-seguro",
                "JARVIS_TRUSTED_DEVICE_ID": "eron-celular-principal",
            },
            clear=False,
        ):
            config.validate()

            context = JarvisServerContext(config=config)
            bootstrap_state = context.bootstrap()
            app = context.build_app()
            client = TestClient(app)

            public_health = client.get("/health")
            protected_health = client.get(
                "/api/health",
                headers={
                    "X-Jarvis-Token": "token-deploy-seguro",
                    "X-Jarvis-Device-Id": "eron-celular-principal",
                },
            )
            panel_response = client.get("/painel")

            self.assertEqual(bootstrap_state["status"], "initialized")
            self.assertEqual(public_health.status_code, 200)
            self.assertEqual(protected_health.status_code, 200)
            self.assertEqual(panel_response.status_code, 200)
            self.assertEqual(public_health.json()["ambiente"]["porta_api"], 8111)
            self.assertTrue(public_health.json()["fila_carregada"])
            self.assertTrue(public_health.json()["memoria_carregada"])
            self.assertTrue(public_health.json()["objetivos_carregados"])
            self.assertTrue(protected_health.json()["configuracao_minima_valida"])
            self.assertTrue(config.startup_report_path.exists())
            self.assertTrue(config.log_file_path.exists())
            self.assertEqual(context.runtime.describe_state()["device_registry_store"], str(device_registry_path))
            self.assertEqual(context.runtime.describe_state()["self_defense_report_path"], str(self_defense_report_path))
            self.assertTrue(device_registry_path.exists())


if __name__ == "__main__":
    unittest.main()
