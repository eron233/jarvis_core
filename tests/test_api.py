"""Testes unitarios para a API real do JARVIS."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from device.device_registry import DeviceRegistry
from executive_planner.audit import AuditLogger
from executive_planner.queue import TaskQueue
from interface.api.app import create_app
from intent_layer.goal_manager import GoalManager
from main import SystemLoopConfig
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.cognitive_evolution import CognitiveEvolutionTracker
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.system_config import JarvisEnvironmentConfig
from security.access_control import AccessControl
from security.iris_instance_policy import IrisInstanceAuthority
from device.iris_mesh import IrisDeviceMesh
from device.iris_state_replication import IrisReplicaSource, IrisReplicaSink, IrisReplicaPullClient
from memory_system.iris_state_store import IrisEncryptedStateStore
from device.iris_task_broker import IrisTaskBroker
from device.iris_node_worker import IrisNodeWorker
from runtime.iris_dialogue_service import IrisDialogueService
from device.iris_inference_tasks import IrisLocalInferenceExecutor


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

    @staticmethod
    def mutation_headers(
        headers: dict[str, str],
        nonce: str = "nonce-teste",
        timestamp: str | None = None,
    ) -> dict[str, str]:
        """Retorna headers autenticados com protecao anti-replay para mutacoes."""

        merged = dict(headers)
        merged["X-Jarvis-Nonce"] = nonce
        merged["X-Jarvis-Timestamp"] = timestamp or datetime.now(timezone.utc).isoformat()
        return merged

    def build_client(self, name: str = "api") -> tuple[TestClient, dict[str, str]]:
        """Monta um cliente FastAPI com runtime isolado para teste."""

        queue_path = make_api_artifact_path(name, "queue")
        semantic_path = make_api_artifact_path(name, "semantic")
        goal_path = make_api_artifact_path(name, "goals")
        device_path = make_api_artifact_path(name, "devices")
        cognitive_path = make_api_artifact_path(name, "cognitive")
        audit_path = make_api_artifact_path(name, "audit")
        for path in (queue_path, semantic_path, goal_path, device_path, cognitive_path, audit_path):
            reset_storage_path(path)

        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=queue_path)
        runtime.goal_manager = GoalManager(storage_path=goal_path)
        runtime.device_registry = DeviceRegistry(storage_path=device_path)
        runtime.cognitive_evolution_tracker = CognitiveEvolutionTracker(storage_path=cognitive_path)
        runtime.audit_logger = AuditLogger(storage_path=audit_path)
        runtime.access_control = AccessControl.from_plaintext("senha-admin-segura-2026")
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
                cognitive_evolution_storage_path=cognitive_path,
                audit_storage_path=audit_path,
                install_signal_handlers=False,
            ),
        )
        return TestClient(app), {
            "X-Jarvis-Token": "token-teste",
            "X-Jarvis-Device-Id": "eron-celular-principal",
        }

    def build_simple_web_client(self, name: str = "api_simple_web") -> TestClient:
        """Monta um cliente com o modo emergencial de login web habilitado."""

        scenario_dir = PROJECT_ROOT / "tests" / "_api_artifacts" / name
        data_dir = scenario_dir / "data"
        logs_dir = scenario_dir / "logs"
        reports_dir = scenario_dir / "reports"
        env = {
            "JARVIS_ENV": "test",
            "JARVIS_TOKEN": "token-teste",
            "JARVIS_TRUSTED_DEVICE_ID": "eron-celular-principal",
            "JARVIS_ADMIN_PASSWORD": "senha-admin-segura-2026",
            "JARVIS_ENABLE_DASHBOARD": "true",
            "JARVIS_SIMPLE_WEB_LOGIN": "true",
            "JARVIS_DATA_DIR": str(data_dir),
            "JARVIS_LOGS_DIR": str(logs_dir),
            "JARVIS_REPORTS_DIR": str(reports_dir),
        }
        config = JarvisEnvironmentConfig.from_env(environ=env, project_root=PROJECT_ROOT)
        runtime = InternalAgentRuntime()
        runtime.access_control = AccessControl.from_plaintext("senha-admin-segura-2026")
        app = create_app(runtime=runtime, deployment_config=config)
        return TestClient(app)

    def test_dialogo_iris_por_api_separa_clientes_e_retem_contexto(self) -> None:
        import secrets
        import tempfile
        from types import SimpleNamespace

        class FakeModel:
            config = SimpleNamespace(enabled=True, offline_mode=True,
                                     allow_remote_endpoints=False)
            def chat(self, **kwargs):
                self.assert_private(kwargs)
                return {"status": "sucesso", "conteudo": "Olá de volta!",
                        "modelo": "llm-local-teste"}
            @staticmethod
            def assert_private(kwargs):
                assert kwargs["allow_external"] is False
                assert kwargs["data_classification"] == "private"

        client, _ = self.build_client("iris_dialogue_api")
        secret = secrets.token_urlsafe(32)
        authority = IrisInstanceAuthority(secret)
        mesh = IrisDeviceMesh(authority)
        broker = IrisTaskBroker(mesh)
        alice = {"instance_id": authority.OWNER_ID, "token": secret}
        bob = authority.create_resident(
            secret, tenant_id="cliente-bob", display_name="Iris Bob",
            user_consented=True,
        )
        offer = mesh.offer_device(
            device_name="Máquina autorizada", device_type="windows",
            surfaces={"compute.infer"}, locally_approved=True,
        )
        node = mesh.approve_offer(
            alice["instance_id"], alice["token"], offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
        )
        def headers(item):
            return {"X-Iris-Instance-Id": item["instance_id"],
                    "X-Iris-Instance-Token": item["token"]}
        node_headers = {
            "X-Iris-Node-Id": node["node_id"],
            "X-Iris-Node-Token": node["node_token"],
        }
        self.assertEqual(
            client.post("/api/iris/dialogue/turn", headers=headers(alice),
                        json={"conversation_id": "my-session", "text": "Olá"}).status_code,
            503,
        )
        with tempfile.TemporaryDirectory() as folder:
            store = IrisEncryptedStateStore(
                Path(folder) / "state.sqlite3", authority,
                root_key=secrets.token_bytes(32),
            )
            try:
                client.app.state.iris_instance_authority = authority
                client.app.state.iris_device_mesh = mesh
                client.app.state.iris_task_broker = broker
                client.app.state.iris_state_store = store
                client.app.state.iris_dialogue_service = IrisDialogueService(broker, store)
                started = client.post(
                    "/api/iris/dialogue/turn", headers=headers(alice),
                    json={"conversation_id": "my-session", "text": "Olá, Íris"},
                )
                self.assertEqual(started.status_code, 200)
                self.assertEqual(started.json()["status"], "queued")
                self.assertEqual(client.post(
                    "/api/iris/dialogue/turn", headers=headers(alice),
                    json={"conversation_id": "my-session", "text": "Outro turno"},
                ).status_code, 409)
                claimed = client.post("/api/iris/no/tarefa/claim",
                                      headers=node_headers)
                self.assertEqual(claimed.status_code, 200)
                ticket = claimed.json()
                self.assertEqual(ticket["operation"], "inference.chat")
                answer = IrisLocalInferenceExecutor(FakeModel()).execute(ticket["payload"])
                accepted = client.post(
                    "/api/iris/no/tarefa/complete",
                    headers=node_headers,
                    json={"job_id": ticket["job_id"],
                          "lease_token": ticket["lease_token"],
                          "result": answer},
                )
                self.assertEqual(accepted.status_code, 200)
                finalized = client.get(
                    "/api/iris/dialogue/my-session/finish",
                    headers=headers(alice),
                )
                self.assertEqual(finalized.status_code, 200)
                self.assertEqual(finalized.json()["content"], "Olá de volta!")
                own = client.get(
                    "/api/iris/dialogue/my-session/history",
                    headers=headers(alice),
                )
                self.assertEqual(len(own.json()["turns"]), 2)
                other = client.get(
                    "/api/iris/dialogue/my-session/history",
                    headers=headers(bob),
                )
                self.assertEqual(other.json()["turns"], [])
                forged = dict(headers(alice), **{
                    "X-Iris-Instance-Token": bob["token"],
                })
                self.assertEqual(client.get(
                    "/api/iris/dialogue/my-session/history", headers=forged,
                ).status_code, 401)
            finally:
                store.close()

    def test_iris_indisponivel_antes_do_bootstrap_explicito(self) -> None:
        client, _ = self.build_client("iris_disabled")
        resp = client.get("/api/iris/instancia", headers={
            "X-Iris-Instance-Id": "iris-original",
            "X-Iris-Instance-Token": "token-qualquer",
        })
        self.assertEqual(resp.status_code, 503)

    def test_iris_residente_nao_tem_acesso_ao_corredor_nem_trade(self) -> None:
        client, _ = self.build_client("iris_isolation")
        authority = IrisInstanceAuthority("owner-secret-seguro-para-teste-" + "x" * 30)
        client.app.state.iris_instance_authority = authority
        alice = authority.create_resident(
            "owner-secret-seguro-para-teste-" + "x" * 30,
            tenant_id="cliente-alice", display_name="Iris Alice", user_consented=True,
        )
        bob = authority.create_resident(
            "owner-secret-seguro-para-teste-" + "x" * 30,
            tenant_id="cliente-bob", display_name="Iris Bob", user_consented=True,
        )
        alice_headers = {
            "X-Iris-Instance-Id": alice["instance_id"],
            "X-Iris-Instance-Token": alice["token"],
        }
        owner_headers = {
            "X-Iris-Instance-Id": IrisInstanceAuthority.OWNER_ID,
            "X-Iris-Instance-Token": "owner-secret-seguro-para-teste-" + "x" * 30,
        }
        me = client.get("/api/iris/instancia", headers=alice_headers)
        self.assertEqual(me.status_code, 200)
        self.assertNotIn("trade.use", me.json()["capabilities"])
        self.assertEqual(client.get("/api/iris/quarto", headers=alice_headers).status_code, 200)
        self.assertEqual(client.get("/api/iris/corredor", headers=alice_headers).status_code, 403)
        self.assertEqual(client.get("/api/iris/feedback/resumo", headers=alice_headers).status_code, 403)
        other_token = dict(alice_headers, **{"X-Iris-Instance-Token": bob["token"]})
        self.assertEqual(client.get("/api/iris/quarto", headers=other_token).status_code, 401)
        authority.set_resident_preferences(
            alice["instance_id"], alice["token"], corridor_visible=True,
        )
        corridor = client.get("/api/iris/corredor", headers=owner_headers)
        self.assertEqual(corridor.status_code, 200)
        self.assertEqual(corridor.json()["quartos"][0]["instance_id"], alice["instance_id"])
        self.assertNotIn("token", corridor.json()["quartos"][0])

    def test_iris_feedback_exige_opt_in_e_codigos_fechados(self) -> None:
        client, _ = self.build_client("iris_feedback")
        secret = "owner-secret-seguro-para-teste-" + "x" * 30
        authority = IrisInstanceAuthority(secret)
        client.app.state.iris_instance_authority = authority
        resident = authority.create_resident(
            secret, tenant_id="cliente-avisos", display_name="Iris", user_consented=True,
        )
        headers = {
            "X-Iris-Instance-Id": resident["instance_id"],
            "X-Iris-Instance-Token": resident["token"],
        }
        denied = client.post("/api/iris/feedback/sinal", headers=headers, json={"code": "slow_response"})
        self.assertEqual(denied.status_code, 200)
        self.assertFalse(denied.json()["registrado"])
        malformed = client.post("/api/iris/feedback/sinal", headers=headers, json={"code": "fala pessoal do cliente"})
        self.assertEqual(malformed.status_code, 422)
        allowed = client.post("/api/iris/preferencias", headers=headers, json={"feedback_opt_in": True})
        self.assertEqual(allowed.status_code, 200)
        recorded = client.post("/api/iris/feedback/sinal", headers=headers, json={"code": "slow_response"})
        self.assertTrue(recorded.json()["registrado"])
        client.post("/api/iris/preferencias", headers=headers, json={"feedback_opt_in": False})
        self.assertEqual(authority.feedback_summary(secret), {})

    def test_iris_mesh_rotas_exigem_malha_injetada(self) -> None:
        client, _ = self.build_client("iris_mesh_unconfigured")
        secret = "segredo-seguro-para-mesh-" + "a" * 32
        authority = IrisInstanceAuthority(secret)
        client.app.state.iris_instance_authority = authority
        owner_headers = {
            "X-Iris-Instance-Id": IrisInstanceAuthority.OWNER_ID,
            "X-Iris-Instance-Token": secret,
        }
        self.assertEqual(
            client.get("/api/iris/dispositivos", headers=owner_headers).status_code,
            503,
        )
        self.assertEqual(
            client.post("/api/iris/dispositivo/heartbeat").status_code,
            503,
        )

    def test_iris_mesh_api_multidispositivo_e_escopo_por_cliente(self) -> None:
        client, _ = self.build_client("iris_mesh_multi")
        secret = "segredo-seguro-para-mesh-" + "a" * 32
        authority = IrisInstanceAuthority(secret)
        mesh = IrisDeviceMesh(authority)
        client.app.state.iris_instance_authority = authority
        client.app.state.iris_device_mesh = mesh
        alice = {"instance_id": authority.OWNER_ID, "token": secret}
        bob = authority.create_resident(
            secret, tenant_id="tenant-bob", display_name="Iris Bob",
            user_consented=True,
        )
        offer = mesh.offer_device(
            device_name="PC da Alice", device_type="windows",
            surfaces={"presence.display", "compute.light"},
            locally_approved=True,
        )
        device = mesh.approve_offer(
            alice["instance_id"], alice["token"],
            offer_id=offer["offer_id"], verification_code=offer["verification_code"],
        )
        alice_headers = {
            "X-Iris-Instance-Id": alice["instance_id"],
            "X-Iris-Instance-Token": alice["token"],
        }
        bob_headers = {
            "X-Iris-Instance-Id": bob["instance_id"],
            "X-Iris-Instance-Token": bob["token"],
        }
        self.assertEqual(
            len(client.get("/api/iris/dispositivos", headers=alice_headers).json()["devices"]),
            1,
        )
        self.assertEqual(
            client.get("/api/iris/dispositivos", headers=bob_headers).status_code,
            403,
        )
        self.assertEqual(
            client.get("/api/iris/continuidade", headers=alice_headers).json()["active_nodes"],
            1,
        )
        routed = client.get(
            "/api/iris/roteamento", params={"recurso": "presence.display"},
            headers=alice_headers,
        )
        self.assertEqual(routed.status_code, 200)
        self.assertEqual(routed.json()["node_id"], device["node_id"])
        self.assertFalse(routed.json()["executed"])
        self.assertEqual(
            client.get("/api/iris/roteamento", params={"recurso": "system.hack"},
                       headers=alice_headers).status_code,
            422,
        )
        self.assertEqual(
            client.post("/api/iris/dispositivo/heartbeat", headers={
                "X-Iris-Node-Id": device["node_id"],
                "X-Iris-Node-Token": device["node_token"],
            }).status_code,
            200,
        )
        self.assertEqual(
            client.post("/api/iris/dispositivo/heartbeat", headers={
                "X-Iris-Node-Id": device["node_id"],
                "X-Iris-Node-Token": bob["token"],
            }).status_code,
            401,
        )

        report = client.post(
            "/api/iris/dispositivo/estado",
            headers={
                "X-Iris-Node-Id": device["node_id"],
                "X-Iris-Node-Token": device["node_token"],
            },
            json={
                "cpu_percent": 30, "memory_available_mb": 2048,
                "battery_percent": None, "latency_ms": 15,
            },
        )
        self.assertEqual(report.status_code, 200)
        self.assertTrue(report.json()["accepted"])
        self.assertEqual(
            client.get("/api/iris/perfis-tecnicos", headers=bob_headers).status_code,
            403,
        )
        profiles = client.get("/api/iris/perfis-tecnicos", headers=alice_headers)
        self.assertEqual(profiles.status_code, 200)
        self.assertEqual(len(profiles.json()["profiles"]), 1)
        self.assertEqual(
            client.post(
                "/api/iris/dispositivo/estado",
                headers={
                    "X-Iris-Node-Id": device["node_id"],
                    "X-Iris-Node-Token": device["node_token"],
                },
                json={
                    "cpu_percent": 500,
                    "memory_available_mb": 2048,
                    "battery_percent": None,
                    "latency_ms": 15,
                },
            ).status_code,
            422,
        )

    def test_iris_estado_persistente_cria_le_e_separa_clientes(self) -> None:
        import secrets
        import tempfile
        client, _ = self.build_client("iris_state_secure")
        secret = "chave-iris-da-original-teste-" + "q" * 32
        authority = IrisInstanceAuthority(secret)
        client.app.state.iris_instance_authority = authority
        alice = authority.create_resident(
            secret, tenant_id="residente-alice", display_name="Alice", user_consented=True,
        )
        bob = authority.create_resident(
            secret, tenant_id="residente-bob", display_name="Bob", user_consented=True,
        )
        def headers(item):
            return {"X-Iris-Instance-Id": item["instance_id"],
                    "X-Iris-Instance-Token": item["token"]}
        self.assertEqual(
            client.get("/api/iris/memoria/teste", headers=headers(alice)).status_code, 503,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = IrisEncryptedStateStore(
                Path(directory) / "segredo.sqlite3", authority,
                root_key=secrets.token_bytes(32),
            )
            client.app.state.iris_state_store = store
            try:
                self.assertEqual(
                    client.get("/api/iris/memoria/teste", headers=headers(alice)).json()["revision"], 0,
                )
                alice_write = client.put(
                    "/api/iris/memoria/teste", headers=headers(alice),
                    json={"expected_revision": 0, "value": {"estado": "privado-alice"}},
                )
                self.assertEqual(alice_write.status_code, 200)
                self.assertEqual(alice_write.json()["revision"], 1)
                bob_read = client.get("/api/iris/memoria/teste", headers=headers(bob))
                self.assertEqual(bob_read.status_code, 200)
                self.assertFalse(bob_read.json()["found"])
                self.assertEqual(
                    client.get("/api/iris/memoria/teste", headers=headers(alice)).json()["value"],
                    {"estado": "privado-alice"},
                )
                clash = client.put(
                    "/api/iris/memoria/teste", headers=headers(alice),
                    json={"expected_revision": 0, "value": {"estado": "esmagar"}},
                )
                self.assertEqual(clash.status_code, 409)
                self.assertEqual(
                    client.get("/api/iris/memoria/documentos", headers=headers(alice)).json()["documents"],
                    [{"document_id": "teste", "revision": 1}],
                )
                self.assertEqual(
                    client.get("/api/iris/memoria/documentos", headers=headers(bob)).json()["documents"],
                    [],
                )
                forged = dict(headers(alice), **{"X-Iris-Instance-Token": bob["token"]})
                self.assertEqual(
                    client.get("/api/iris/memoria/teste", headers=forged).status_code, 401,
                )
                authority.revoke(IrisInstanceAuthority.OWNER_ID, secret, alice["instance_id"])
                self.assertEqual(
                    client.get("/api/iris/memoria/teste", headers=headers(alice)).status_code, 401,
                )
            finally:
                store.close()

    def test_iris_broker_http_computacao_por_no_autorizado(self) -> None:
        import secrets
        client, _ = self.build_client("iris_broker_http")
        secret = secrets.token_urlsafe(32)
        authority = IrisInstanceAuthority(secret)
        mesh = IrisDeviceMesh(authority)
        broker = IrisTaskBroker(mesh)
        client.app.state.iris_instance_authority = authority
        client.app.state.iris_device_mesh = mesh
        client.app.state.iris_task_broker = broker
        person = {"instance_id": authority.OWNER_ID, "token": secret}
        offer = mesh.offer_device(
            device_name="Notebook", device_type="windows",
            surfaces={"compute.light"}, locally_approved=True,
        )
        node = mesh.approve_offer(
            person["instance_id"], person["token"],
            offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
        )
        resident_headers = {
            "X-Iris-Instance-Id": person["instance_id"],
            "X-Iris-Instance-Token": person["token"],
        }
        node_headers = {
            "X-Iris-Node-Id": node["node_id"],
            "X-Iris-Node-Token": node["node_token"],
        }
        job = client.post("/api/iris/tarefas", headers=resident_headers, json={
            "operation": "math.sum", "payload": {"values": [1, 2, 3]},
        })
        self.assertEqual(job.status_code, 200)
        self.assertEqual(job.json()["status"], "queued")
        claim = client.post("/api/iris/no/tarefa/claim", headers=node_headers)
        self.assertEqual(claim.status_code, 200)
        self.assertEqual(claim.json()["status"], "leased")
        ticket = claim.json()
        done = client.post("/api/iris/no/tarefa/complete", headers=node_headers, json={
            "job_id": ticket["job_id"],
            "lease_token": ticket["lease_token"],
            "result": {"sum": 6.0},
        })
        self.assertEqual(done.status_code, 200)
        self.assertFalse(done.json()["verified"])
        details = client.get(
            "/api/iris/tarefas/" + ticket["job_id"],
            headers=resident_headers,
        )
        self.assertEqual(details.json()["result"], {"sum": 6.0})
        repeated = client.post("/api/iris/no/tarefa/complete", headers=node_headers, json={
            "job_id": ticket["job_id"],
            "lease_token": ticket["lease_token"],
            "result": {"sum": 6.0},
        })
        self.assertEqual(repeated.status_code, 403)
        reject = client.post("/api/iris/tarefas", headers=resident_headers, json={
            "operation": "shell.exec", "payload": {"command": "whoami"},
        })
        self.assertEqual(reject.status_code, 422)
        self.assertEqual(client.post(
            "/api/iris/no/tarefa/claim",
            headers={"X-Iris-Node-Id": node["node_id"],
                     "X-Iris-Node-Token": person["token"]},
        ).status_code, 403)

    def test_iris_worker_cliente_real_com_protocolo_http_sem_socket_externo(self):
        import secrets
        client, _ = self.build_client("iris_worker_local")
        secret = secrets.token_urlsafe(32)
        authority = IrisInstanceAuthority(secret)
        mesh = IrisDeviceMesh(authority)
        client.app.state.iris_instance_authority = authority
        client.app.state.iris_device_mesh = mesh
        client.app.state.iris_task_broker = IrisTaskBroker(mesh)
        person = {"instance_id": authority.OWNER_ID, "token": secret}
        offer = mesh.offer_device(
            device_name="PC", device_type="windows",
            surfaces={"compute.light"}, locally_approved=True,
        )
        node = mesh.approve_offer(
            person["instance_id"], person["token"],
            offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
        )
        class LocalTestClientWorker(IrisNodeWorker):
            def _post(self, path, payload=None):
                response = client.post(path, json=payload or {}, headers={
                    "X-Iris-Node-Id": self.node_id,
                    "X-Iris-Node-Token": self._node_token,
                })
                if response.status_code != 200:
                    raise RuntimeError(response.text)
                return response.json()

        worker = LocalTestClientWorker(
            "http://localhost", node["node_id"], node["node_token"],
        )
        headers = {
            "X-Iris-Instance-Id": person["instance_id"],
            "X-Iris-Instance-Token": person["token"],
        }
        task = client.post("/api/iris/tarefas", headers=headers, json={
            "operation": "hash.sha256", "payload": {"text": "Iris"},
        }).json()
        done = worker.run_once()
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["job_id"], task["job_id"])
        self.assertEqual(
            client.get("/api/iris/tarefas/" + task["job_id"], headers=headers).json()["result"]["sha256"],
            __import__("hashlib").sha256("Iris".encode()).hexdigest(),
        )
        self.assertEqual(worker.run_once()["status"], "idle")

    def test_iris_replica_api_pareada_e_isolada_entre_clientes(self) -> None:
        import secrets
        import tempfile
        from pathlib import Path
        client, _ = self.build_client("iris_replica_http")
        secret = secrets.token_urlsafe(32)
        auth = IrisInstanceAuthority(secret)
        mesh = IrisDeviceMesh(auth)
        client.app.state.iris_instance_authority = auth
        client.app.state.iris_device_mesh = mesh
        with tempfile.TemporaryDirectory() as folder:
            store = IrisEncryptedStateStore(
                Path(folder) / "source.db", auth, root_key=secrets.token_bytes(32),
            )
            target = IrisEncryptedStateStore(
                Path(folder) / "target.db", auth, root_key=secrets.token_bytes(32),
            )
            try:
                alice = {"instance_id": auth.OWNER_ID, "token": secret}
                bob = auth.create_resident(
                    secret, tenant_id="cliente-bob", display_name="Iris Bob",
                    user_consented=True,
                )
                store.put(alice["instance_id"], alice["token"], "historia",
                          {"lembranca": "somente Alice"}, expected_revision=0)
                store.put(bob["instance_id"], bob["token"], "historico",
                          {"segredo": "Bob"}, expected_revision=0)
                offer = mesh.offer_device(
                    device_name="PC secundario", device_type="linux",
                    surfaces={"memory.sync"}, locally_approved=True,
                )
                node = mesh.approve_offer(
                    alice["instance_id"], alice["token"],
                    offer_id=offer["offer_id"],
                    verification_code=offer["verification_code"],
                )
                client.app.state.iris_state_store = store
                client.app.state.iris_replica_source = IrisReplicaSource(
                    mesh, store, source_id="iris-source-primary-test",
                )
                headers = {
                    "X-Iris-Node-Id": node["node_id"],
                    "X-Iris-Node-Token": node["node_token"],
                }
                manifest = client.get("/api/iris/replication/manifest", headers=headers)
                self.assertEqual(manifest.status_code, 200)
                self.assertEqual(
                    manifest.json()["documents"], [{"document_id": "historia", "revision": 1}],
                )
                sink = IrisReplicaSink(
                    target, node_id=node["node_id"], node_token=node["node_token"],
                    instance_id=alice["instance_id"],
                    source_id="iris-source-primary-test",
                )
                def remote_get(path, request_headers):
                    response = client.get(path, headers=request_headers)
                    self.assertEqual(response.status_code, 200)
                    return response.json()
                pull = IrisReplicaPullClient(
                    "https://remote.invalid", sink, transport=remote_get,
                )
                self.assertEqual(pull.sync_once()["applied"], 1)
                self.assertEqual(target.get(
                    alice["instance_id"], alice["token"], "historia",
                )["value"], {"lembranca": "somente Alice"})
                self.assertFalse(target.get(
                    bob["instance_id"], bob["token"], "historico",
                )["found"])
                self.assertEqual(client.get(
                    "/api/iris/replication/manifest",
                    headers={"X-Iris-Node-Id": node["node_id"],
                             "X-Iris-Node-Token": bob["token"]},
                ).status_code, 403)
                mesh.disconnect(
                    alice["instance_id"], alice["token"], node_id=node["node_id"],
                )
                self.assertEqual(client.get(
                    "/api/iris/replication/manifest", headers=headers,
                ).status_code, 403)
            finally:
                target.close()
                store.close()

    def test_iris_replica_ausente_falha_fechado(self) -> None:
        client, _ = self.build_client("iris_replica_off")
        self.assertEqual(client.get(
            "/api/iris/replication/manifest",
        ).status_code, 503)

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
            headers=self.mutation_headers(headers, nonce="task-1"),
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

        cycle_response = client.post(
            "/api/ciclos/executar",
            headers=self.mutation_headers(headers, nonce="cycle-1"),
        )
        self.assertEqual(cycle_response.status_code, 200)
        self.assertEqual(cycle_response.json()["resultado"]["status"], "executed")

        goals_response = client.get("/api/objetivos", headers=headers)
        self.assertEqual(goals_response.status_code, 200)
        self.assertEqual(goals_response.json()["dados"]["resumo"]["objetivos_concluidos"], 1)

        memory_response = client.get("/api/memoria/recente?limit=3", headers=headers)
        self.assertEqual(memory_response.status_code, 200)
        self.assertGreaterEqual(len(memory_response.json()["entradas_semanticas"]), 1)

        report_response = client.get("/api/relatorio/sistema", headers=headers)
        self.assertEqual(report_response.status_code, 200)
        report_payload = report_response.json()
        self.assertEqual(report_payload["saude_runtime"]["status"], "ok")
        self.assertEqual(report_payload["objetivos"]["objetivos_concluidos"], 1)

    def test_api_comando_responde_frase_especial_para_voz_admin(self) -> None:
        """Confirma a resposta reservada quando a voz reconhecida e do admin."""

        client, headers = self.build_client("command_special")

        response = client.post(
            "/api/comando",
            headers=self.mutation_headers(headers, nonce="command-special"),
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
            headers=self.mutation_headers(headers, nonce="command-ignore"),
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
            headers=self.mutation_headers(headers, nonce="command-guest"),
            json={"texto": "executar ciclo"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "denied")
        self.assertEqual(payload["motivo"], "guest_restricted_command")

    def test_api_expoe_mapa_e_analise_de_evolucao_cognitiva(self) -> None:
        """Garante acesso ao historico cognitivo e ao comando textual de evolucao."""

        client, headers = self.build_client("cognitive_evolution")

        report_response = client.get("/api/cognicao/evolucao?nivel=historica", headers=headers)
        self.assertEqual(report_response.status_code, 200)
        report_payload = report_response.json()
        self.assertIn("regioes", report_payload)
        self.assertIn("trilhas_aprendizado", report_payload)
        self.assertIn("resumo", report_payload)

        analysis_response = client.get("/api/cognicao/evolucao/analise?nivel=historica", headers=headers)
        self.assertEqual(analysis_response.status_code, 200)
        analysis_payload = analysis_response.json()
        self.assertIn("regioes_mais_utilizadas", analysis_payload)
        self.assertIn("conexoes_mais_fortes", analysis_payload)

        command_response = client.post(
            "/api/comando",
            headers=self.mutation_headers(headers, nonce="command-evolution"),
            json={"texto": "Jarvis, mostre sua evolucao"},
        )
        self.assertEqual(command_response.status_code, 200)
        command_payload = command_response.json()
        self.assertEqual(command_payload["acao"], "cognitive_evolution_visualization")
        self.assertIn("regioes", command_payload["dados_relacionados"])

    def test_api_rejeita_replay_em_operacao_mutante(self) -> None:
        """Garante que a API negue reutilizacao do mesmo nonce em mutacao."""

        client, headers = self.build_client("replay")
        protected_headers = self.mutation_headers(
            headers,
            nonce="nonce-repetido",
        )

        first_response = client.post(
            "/api/comando",
            headers=protected_headers,
            json={"texto": "status"},
        )
        second_response = client.post(
            "/api/comando",
            headers=protected_headers,
            json={"texto": "status"},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 403)
        self.assertEqual(second_response.json()["detail"], "Requisicao repetida detectada.")

    def test_api_expoe_identidade_do_runtime_em_endpoint_dedicado(self) -> None:
        """Confirma rastreabilidade explicita do runtime que esta respondendo."""

        client, headers = self.build_client("runtime_identity")

        response = client.get("/api/runtime/identidade", headers=headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()["dados"]
        self.assertIn("commit", payload)
        self.assertIn("boot_timestamp", payload)
        self.assertIn("entrypoint", payload)

    def test_api_nao_expone_mais_alias_duplicado_de_relatorio(self) -> None:
        """Garante que o alias antigo de relatorio nao continue ativo."""

        client, headers = self.build_client("report_alias_removed")

        response = client.get("/api/relatorio", headers=headers)

        self.assertEqual(response.status_code, 404)

    def test_api_permite_endpoints_protegidos_com_sessao_web_simples(self) -> None:
        """Confirma que a sessao web simples substitui token e device no painel."""

        client = self.build_simple_web_client("runtime_identity_simple")

        denied_response = client.post(
            "/api/auth/device-session",
            headers=self.mutation_headers({}, nonce="simple-auth-invalid"),
            json={"admin_password": "senha-errada"},
        )
        self.assertEqual(denied_response.status_code, 401)
        self.assertEqual(denied_response.json()["detail"], "Senha administrativa invalida.")

        session_response = client.post(
            "/api/auth/device-session",
            headers=self.mutation_headers({}, nonce="simple-auth-valid"),
            json={"admin_password": "senha-admin-segura-2026"},
        )
        self.assertEqual(session_response.status_code, 200)
        self.assertEqual(session_response.json()["modo"], "simple_web_login")

        status_response = client.get("/api/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["dados"]["status"], "initialized")

        health_response = client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertTrue(health_response.json()["configuracao_minima_valida"])

        last_access = client.app.state.runtime.get_access_events(limit=1)[0]
        self.assertEqual(last_access["payload"]["device_id"], "web-access-recovery")

    def test_api_persiste_tarefa_no_store_configurado_apos_enfileiramento(self) -> None:
        """Garante que a rota real de tarefas grave no store persistente configurado."""

        client, headers = self.build_client("task_persistence")

        response = client.post(
            "/api/tarefas",
            headers=self.mutation_headers(headers, nonce="task-persist"),
            json={
                "task_id": "persist-api-1",
                "goal": "Persistir tarefa real",
                "description": "Conferir escrita duravel da fila",
                "domain": "runtime",
                "impact": 3,
                "urgency": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        queue_path = client.app.state.runtime.task_queue.storage_path
        self.assertTrue(queue_path.exists())
        snapshot = queue_path.read_text(encoding="utf-8")
        self.assertIn("persist-api-1", snapshot)


if __name__ == "__main__":
    unittest.main()
