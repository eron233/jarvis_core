"""Testes unitarios para os relatorios operacionais completos do JARVIS."""

from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.queue import TaskQueue
from interface.api.app import create_app
from intent_layer.goal_manager import GoalManager
from main import SystemLoopConfig
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_report_artifact_path(name: str, suffix: str) -> Path:
    return PROJECT_ROOT / "tests" / "_api_artifacts" / f"{name}_{suffix}.json"


def reset_storage_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class OperationalReportsTests(unittest.TestCase):
    def build_client(self, name: str = "reports") -> tuple[TestClient, dict[str, str]]:
        queue_path = make_report_artifact_path(name, "queue")
        semantic_path = make_report_artifact_path(name, "semantic")
        goal_path = make_report_artifact_path(name, "goals")
        reset_storage_path(queue_path)
        reset_storage_path(semantic_path)
        reset_storage_path(goal_path)

        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=queue_path)
        runtime.goal_manager = GoalManager(storage_path=goal_path)
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=semantic_path),
            "procedural": ProceduralMemory(),
        }

        app = create_app(
            runtime=runtime,
            api_token="token-teste",
            trusted_device_id="eron-celular-principal",
            config=SystemLoopConfig(
                queue_storage_path=queue_path,
                semantic_storage_path=semantic_path,
                install_signal_handlers=False,
            ),
        )
        client = TestClient(app)
        headers = {
            "X-Jarvis-Token": "token-teste",
            "X-Jarvis-Device-Id": "eron-celular-principal",
        }
        return client, headers

    def seed_runtime(self, client: TestClient, headers: dict[str, str]) -> None:
        active_goal = client.app.state.runtime.goal_manager.add_active_goal(
            title="Preparar revisao operacional",
            description="Objetivo para gerar historico de relatorios",
            priority=5,
        )
        client.post(
            "/api/tarefas",
            headers=headers,
            json={
                "task_id": "report-task-1",
                "goal": "Preparar revisao operacional",
                "description": "Executar tarefa base para relatorios",
                "domain": "runtime",
                "impact": 3,
                "urgency": 2,
                "parent_goal_id": active_goal["goal_id"],
            },
        )
        client.post("/api/ciclos/executar", headers=headers)
        denied_headers = dict(headers)
        denied_headers["X-Jarvis-Device-Id"] = "device-indevido"
        client.get("/api/status", headers=denied_headers)

    def test_healthcheck_rico_exige_autenticacao_e_device_confiavel(self) -> None:
        client, headers = self.build_client("health_report")

        denied_response = client.get("/api/health")
        self.assertEqual(denied_response.status_code, 401)

        allowed_response = client.get("/api/health", headers=headers)
        self.assertEqual(allowed_response.status_code, 200)
        payload = allowed_response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["api_ativa"])
        self.assertTrue(payload["runtime_ativo"])
        self.assertTrue(payload["planner_acoplado"])
        self.assertTrue(payload["token_configurado"])
        self.assertTrue(payload["dispositivo_confiavel_configurado"])

    def test_endpoints_de_relatorio_retorna_campos_principais(self) -> None:
        client, headers = self.build_client("all_reports")
        self.seed_runtime(client, headers)

        system_response = client.get("/api/relatorio/sistema", headers=headers)
        queue_response = client.get("/api/relatorio/fila", headers=headers)
        goals_response = client.get("/api/relatorio/objetivos", headers=headers)
        memory_response = client.get("/api/relatorio/memoria", headers=headers)
        audit_response = client.get("/api/relatorio/auditoria", headers=headers)

        self.assertEqual(system_response.status_code, 200)
        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(goals_response.status_code, 200)
        self.assertEqual(memory_response.status_code, 200)
        self.assertEqual(audit_response.status_code, 200)

        system_payload = system_response.json()
        queue_payload = queue_response.json()
        goals_payload = goals_response.json()
        memory_payload = memory_response.json()
        audit_payload = audit_response.json()

        self.assertIn("uptime_segundos", system_payload)
        self.assertIn("estado_do_planner", system_payload)
        self.assertIn("quantidade_tarefas_concluidas", system_payload)
        self.assertIn("ultimas_falhas_registradas", system_payload)

        self.assertIn("resumo", queue_payload)
        self.assertIn("principais_tarefas", queue_payload)
        self.assertIn("tarefas_aguardando_aprovacao", queue_payload["resumo"])

        self.assertIn("metas_estrategicas", goals_payload)
        self.assertIn("objetivos_ativos", goals_payload)
        self.assertIn("tarefas_na_fila", goals_payload["objetivos_ativos"][0])

        self.assertIn("resumo", memory_payload)
        self.assertIn("memorias_recentes", memory_payload)
        self.assertIn("memorias_por_dominio", memory_payload)
        self.assertTrue(memory_payload["resumo"]["integridade_basica"]["json_valido"])

        self.assertIn("ultimas_decisoes_planner", audit_payload)
        self.assertIn("ultimos_acessos", audit_payload)
        self.assertIn("ultimas_tentativas_negadas", audit_payload)
        self.assertGreaterEqual(len(audit_payload["ultimas_tentativas_negadas"]), 1)
