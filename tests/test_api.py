"""Testes unitarios para a API real do JARVIS."""

from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from device.device_registry import DeviceRegistry
from executive_planner.queue import TaskQueue
from interface.api.app import create_app
from intent_layer.goal_manager import GoalManager
from main import SystemLoopConfig
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_api_artifact_path(name: str, suffix: str) -> Path:
    """Retorna o path isolado usado pelos testes da API."""

    return PROJECT_ROOT / "tests" / "_api_artifacts" / f"{name}_{suffix}.json"


def reset_storage_path(path: Path) -> None:
    """Garante que o arquivo de artefato de teste comece vazio."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class JarvisApiTests(unittest.TestCase):
    """Valida a inicializacao, autenticacao e operacao basica da API."""

    def build_client(self, name: str = "api") -> tuple[TestClient, dict[str, str]]:
        """Monta um cliente FastAPI com runtime isolado para teste."""

        queue_path = make_api_artifact_path(name, "queue")
        semantic_path = make_api_artifact_path(name, "semantic")
        goal_path = make_api_artifact_path(name, "goals")
        device_path = make_api_artifact_path(name, "devices")
        for path in (queue_path, semantic_path, goal_path, device_path):
            reset_storage_path(path)

        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=queue_path)
        runtime.goal_manager = GoalManager(storage_path=goal_path)
        runtime.device_registry = DeviceRegistry(storage_path=device_path)
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
        return TestClient(app), {
            "X-Jarvis-Token": "token-teste",
            "X-Jarvis-Device-Id": "eron-celular-principal",
        }

    def test_api_inicializa_e_responde_healthcheck(self) -> None:
        """Confirma que o healthcheck simples responde com a API ativa."""

        client, _headers = self.build_client("health")

        response = client.get("/api/saude")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["status_ptbr"], "saudavel")

    def test_api_exige_token_nos_endpoints_protegidos(self) -> None:
        """Garante que endpoints protegidos rejeitem chamadas sem token."""

        client, _headers = self.build_client("auth_missing_headers")

        response = client.get("/api/status")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Token de acesso ausente.")
        last_denied = client.app.state.runtime.get_access_events(limit=1, denied_only=True)[0]
        self.assertEqual(last_denied["payload"]["reason"], "missing_token")

    def test_api_permite_acesso_com_token_e_device_corretos(self) -> None:
        """Confirma acesso autorizado quando token e device estao corretos."""

        client, headers = self.build_client("authorized")

        response = client.get("/api/status", headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dados"]["status"], "initialized")
        last_access = client.app.state.runtime.get_access_events(limit=1)[0]
        self.assertEqual(last_access["payload"]["status"], "authorized")

    def test_api_nega_acesso_com_token_invalido(self) -> None:
        """Verifica negacao e auditoria para token invalido."""

        client, headers = self.build_client("invalid_token")
        headers["X-Jarvis-Token"] = "token-errado"

        response = client.get("/api/status", headers=headers)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Token de acesso invalido.")
        last_denied = client.app.state.runtime.get_access_events(limit=1, denied_only=True)[0]
        self.assertEqual(last_denied["payload"]["reason"], "invalid_token")

    def test_api_nega_acesso_com_device_invalido(self) -> None:
        """Verifica negacao e auditoria para dispositivo nao confiavel."""

        client, headers = self.build_client("invalid_device")
        headers["X-Jarvis-Device-Id"] = "celular-nao-autorizado"

        response = client.get("/api/status", headers=headers)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Dispositivo nao autorizado.")
        last_denied = client.app.state.runtime.get_access_events(limit=1, denied_only=True)[0]
        self.assertEqual(last_denied["payload"]["reason"], "untrusted_device")

    def test_endpoints_principais_operam_sobre_runtime_real(self) -> None:
        """Executa o fluxo principal da API sobre um runtime real de teste."""

        client, headers = self.build_client("core")

        goal_response = client.app.state.runtime.goal_manager.add_active_goal(
            title="Organizar estudo semanal",
            description="Objetivo operacional de estudo",
            priority=6,
        )

        task_response = client.post(
            "/api/tarefas",
            headers=headers,
            json={
                "task_id": "api-task-1",
                "goal": "Organizar estudo semanal",
                "description": "Revisar plano de estudo",
                "domain": "study",
                "impact": 2,
                "urgency": 3,
                "parent_goal_id": goal_response["goal_id"],
            },
        )
        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(task_response.json()["tarefa"]["parent_goal_id"], goal_response["goal_id"])

        list_response = client.get("/api/tarefas", headers=headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 1)

        cycle_response = client.post("/api/ciclos/executar", headers=headers)
        self.assertEqual(cycle_response.status_code, 200)
        self.assertEqual(cycle_response.json()["resultado"]["status"], "executed")

        goals_response = client.get("/api/objetivos", headers=headers)
        self.assertEqual(goals_response.status_code, 200)
        self.assertEqual(goals_response.json()["dados"]["resumo"]["objetivos_concluidos"], 1)

        memory_response = client.get("/api/memoria/recente?limit=3", headers=headers)
        self.assertEqual(memory_response.status_code, 200)
        self.assertGreaterEqual(len(memory_response.json()["entradas_semanticas"]), 1)

        report_response = client.get("/api/relatorio", headers=headers)
        self.assertEqual(report_response.status_code, 200)
        report_payload = report_response.json()
        self.assertEqual(report_payload["saude_runtime"]["status"], "ok")
        self.assertEqual(report_payload["objetivos"]["objetivos_concluidos"], 1)

    def test_api_comando_responde_frase_especial_para_voz_admin(self) -> None:
        """Confirma a resposta reservada quando a voz reconhecida e do admin."""

        client, headers = self.build_client("command_special")

        response = client.post(
            "/api/comando",
            headers=headers,
            json={"texto": "Jarvis ta ai", "voz_identificada": "eron"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resposta"], "Sim, Sr. Maciel.")
        self.assertEqual(payload["acao"], "special_phrase")

    def test_api_comando_ignora_frase_especial_sem_voz_admin(self) -> None:
        """Garante que a frase reservada seja ignorada quando a voz nao e reconhecida."""

        client, headers = self.build_client("command_ignore")

        response = client.post(
            "/api/comando",
            headers=headers,
            json={"texto": "Jarvis ta ai", "voz_identificada": "visitante"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ignored")
        self.assertFalse(payload["respondido"])

    def test_api_comando_restringe_execucao_sensivel_em_modo_guest(self) -> None:
        """Verifica que guest pode consultar, mas nao rodar ciclo sensivel sem admin."""

        client, headers = self.build_client("command_guest")

        response = client.post(
            "/api/comando",
            headers=headers,
            json={"texto": "executar ciclo"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "denied")
        self.assertEqual(payload["motivo"], "guest_restricted_command")


if __name__ == "__main__":
    unittest.main()
