"""Agencia real: inferencia local, limites, governanca e testes de API."""
import json
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from interface.api.app import create_app
from runtime.agent_agency import AgentAgency
from runtime.internal_agent_runtime import InternalAgentRuntime

GOOD = json.dumps({"veredito": "aprovado", "problemas": []}, ensure_ascii=False)
BAD = json.dumps({"veredito": "reprovado", "problemas": ["Faltam testes reais."]}, ensure_ascii=False)


class FakeInferenceRouter:
    def __init__(self, *, responses=None, endpoint="http://127.0.0.1:8080/v1",
                 provider_order=("llamacpp", "ollama", "freellmapi"), enabled=True):
        self.config = SimpleNamespace(enabled=enabled, provider_order=provider_order)
        self.backends = {
            "llamacpp": SimpleNamespace(base_url=endpoint),
            "ollama": SimpleNamespace(base_url="http://127.0.0.1:11434/v1"),
            "freellmapi": SimpleNamespace(base_url="http://127.0.0.1:3001/v1"),
        }
        self.responses = list(responses or [
            {"status": "sucesso", "conteudo": "Implementacao hipotetica de usuario. sem deploy.",
             "modelo": "local-1", "provider": "llamacpp", "usage": {"total_tokens": 20}},
            {"status": "sucesso", "conteudo": GOOD, "modelo": "local-1", "provider": "llamacpp"},
            {"status": "sucesso", "conteudo": GOOD, "modelo": "local-1", "provider": "llamacpp"},
        ])
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if not self.responses:
            raise RuntimeError("No fake response configured")
        return self.responses.pop(0)


class AgencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.router = FakeInferenceRouter()
        self.agency = AgentAgency(
            inference_router=self.router, record_dir=Path(self.tmp.name),
            enabled=True,
        )

    def test_catalogo_sem_copiar_prompts_de_terceiros(self):
        data = self.agency.specialists()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["maximo_chamadas_modelo"], 3)
        self.assertFalse(data["ferramentas_executaveis"])
        self.assertGreaterEqual(len(data["agentes"]), 4)
        self.assertIn("engenharia", {x["id"] for x in data["agentes"]})

    def test_plano_sem_execucao_ou_efeitos_colaterais(self):
        out = self.agency.plan(goal="Construir editor de audio",
                               discipline="engenharia", criteria=["suporte WAV"])
        self.assertEqual(out["status"], "planejado")
        self.assertEqual(len(out["etapas"]), 3)
        self.assertEqual([x["agente"] for x in out["etapas"]],
                         ["engenharia", "seguranca", "qualidade"])
        self.assertFalse(out["modelo_ou_ferramenta_executados"])
        self.assertFalse(self.router.calls)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_validacao_e_limites_de_entrada(self):
        cases = [
            ("", "engenharia", None), ("x" * 1801, "engenharia", None),
            ("ok", "unknown", None), ("ok", "qualidade", None),
            ("ok", "engenharia", ["x"] * 7),
            ("ok", "engenharia", [123]),
            ("ok", "engenharia", ["x" * 301]),
        ]
        for goal, discipline, criteria in cases:
            with self.subTest(goal=goal[:10], discipline=discipline):
                result = self.agency.execute(
                    goal=goal, discipline=discipline,
                    criteria=criteria, approved=True,
                )
                self.assertEqual(result["status"], "entrada_invalida")
        self.assertEqual(self.router.calls, [])

    def test_agencia_desabilitada_e_sem_aprovacao(self):
        off = AgentAgency(inference_router=self.router,
                          record_dir=Path(self.tmp.name), enabled=False)
        self.assertEqual(off.execute(goal="teste", approved=True)["status"], "desabilitado")
        self.assertEqual(self.agency.execute(goal="teste")["status"], "aguardando_aprovacao")
        self.assertFalse(self.router.calls)

    def test_runtime_ausente_ou_backend_remoto_bloqueado(self):
        no_inference = FakeInferenceRouter(enabled=False)
        s = AgentAgency(inference_router=no_inference,
                        record_dir=Path(self.tmp.name), enabled=True)
        self.assertEqual(s.execute(goal="texto", approved=True)["status"], "indisponivel")
        remote = FakeInferenceRouter(endpoint="https://external.example/v1",
                                     provider_order=("llamacpp", "freellmapi"))
        s = AgentAgency(inference_router=remote,
                        record_dir=Path(self.tmp.name), enabled=True)
        self.assertEqual(s.execute(goal="texto", approved=True)["status"], "indisponivel")
        self.assertEqual(remote.calls, [])

    def test_freellmapi_nao_recebe_prompt_mesmo_disponivel(self):
        remote_only = FakeInferenceRouter(provider_order=("freellmapi",))
        s = AgentAgency(inference_router=remote_only,
                        record_dir=Path(self.tmp.name), enabled=True)
        out = s.execute(goal="pesquisa privada", approved=True)
        self.assertEqual(out["status"], "indisponivel")
        self.assertEqual(remote_only.calls, [])

    def test_three_real_calls_are_recorded_no_homologation(self):
        secret = "Ideia particular que nao deve persistir em claro"
        out = self.agency.execute(
            goal=secret, discipline="engenharia",
            criteria=["sem falsos positivos"], approved=True,
        )
        self.assertEqual(out["status"], "rascunho_revisado_nao_homologado")
        self.assertEqual(out["executado"], True)
        self.assertTrue(out["auditoria_persistida"])
        self.assertFalse(out["software_homologado"])
        self.assertFalse(out["revisao_independente_comprovada"])
        self.assertEqual(len(self.router.calls), 3)
        self.assertEqual([v["agente"] for v in out["rastreio"]],
                         ["engenharia", "seguranca", "qualidade"])
        self.assertEqual(out["entrega_textual"],
                         "Implementacao hipotetica de usuario. sem deploy.")
        for messages, kwargs in self.router.calls:
            self.assertEqual(kwargs["provider"], "llamacpp")
            self.assertFalse(kwargs["allow_external"])
            self.assertEqual(kwargs["data_classification"], "private")
            self.assertIsNone(kwargs["tools"])
            self.assertLessEqual(kwargs["max_tokens"], 512)
            self.assertEqual(messages[0]["role"], "system")
        path = Path(self.tmp.name) / (out["execucao_id"] + ".json")
        stored = path.read_text(encoding="utf-8")
        self.assertNotIn(secret, stored)
        self.assertNotIn("Implementacao hipotetica", stored)
        self.assertIn("objetivo_sha256", stored)
        self.assertEqual(json.loads(stored)["chamadas_concluidas"], 3)

    def test_negative_review_blocks_approval(self):
        self.router.responses[1]["conteudo"] = BAD
        result = self.agency.execute(goal="Programa", approved=True)
        self.assertEqual(result["status"], "revisao_reprovada")
        self.assertEqual(result["avaliacoes"][0]["parecer"]["veredito"], "reprovado")
        self.assertFalse(result["software_homologado"])

    def test_invalid_reviewer_json_fails_closed(self):
        self.router.responses[1]["conteudo"] = "aprovado sem evidencias"
        out = self.agency.execute(goal="Programa", approved=True)
        self.assertEqual(out["status"], "revisao_inconclusiva")
        self.assertEqual(len(self.router.calls), 2)
        self.assertEqual(out["avaliacoes"][0]["status"], "inconclusivo")

    def test_failure_from_executor_stops_without_fake_review(self):
        self.router.responses[0] = {"status": "indisponivel", "motivo": "nao ha modelo"}
        out = self.agency.execute(goal="Programa", approved=True)
        self.assertEqual(out["status"], "incompleto")
        self.assertFalse(out["executado"])
        self.assertIsNone(out["entrega_textual"])
        self.assertEqual(len(self.router.calls), 1)
        self.assertEqual(out["avaliacoes"], [])

    def test_no_tool_calls_and_truncated_outputs(self):
        for extra in [{"tool_calls": [{"id": "danger"}]},
                      {"finish_reason": "length"}]:
            with self.subTest(extra=extra):
                fake = FakeInferenceRouter()
                fake.responses[0].update(extra)
                engine = AgentAgency(inference_router=fake,
                                     record_dir=Path(self.tmp.name), enabled=True)
                out = engine.execute(goal="Nenhuma execucao", approved=True)
                self.assertEqual(out["status"], "incompleto")
                self.assertEqual(len(fake.calls), 1)

    def test_reviewer_not_independent_when_same_model(self):
        out = self.agency.execute(goal="Software", approved=True)
        self.assertFalse(out["modelos_distintos"])
        self.assertFalse(out["revisao_independente_comprovada"])

    def test_budget_one_production_and_two_reviews(self):
        out = self.agency.execute(goal="Investigacao", discipline="seguranca",
                                  approved=True)
        self.assertEqual(len(self.router.calls), 3)
        self.assertEqual([x["agente"] for x in out["rastreio"]],
                         ["seguranca", "engenharia", "qualidade"])

    def test_review_parser_requires_strict_json(self):
        for bad in [
            "opinion", "{}", "[]",
            '{"veredito":"sim","problemas":[]}',
            '{"veredito":"aprovado","problemas":["x"]}',
            '{"veredito":"aprovado","problemas":"vazio"}',
            '{"veredito":"reprovado","problemas":[12]}',
        ]:
            self.assertIsNone(self.agency._read_review(bad))


class AgencyAPITests(unittest.TestCase):
    def setUp(self):
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()
        self.client = TestClient(create_app(
            runtime=self.runtime, api_token="agency-secret-test",
            trusted_device_id="agency-local-test",
        ))

    @staticmethod
    def _headers():
        return {
            "X-Jarvis-Token": "agency-secret-test",
            "X-Jarvis-Device-Id": "agency-local-test",
            "X-Jarvis-Nonce": str(uuid.uuid4()),
            "X-Jarvis-Timestamp": str(int(time.time())),
        }

    def test_endpoints_protected(self):
        self.assertNotEqual(self.client.get("/api/agencia/especialistas").status_code, 200)
        self.assertNotEqual(self.client.post(
            "/api/agencia/planejar", json={"objetivo": "teste"},
        ).status_code, 200)
        self.assertNotEqual(self.client.post(
            "/api/agencia/executar", json={"objetivo": "teste", "aprovado": True},
        ).status_code, 200)

    def test_planning_real_route_without_model(self):
        out = self.client.post(
            "/api/agencia/planejar",
            headers=self._headers(),
            json={"objetivo": "Analisar componentes", "especialidade": "engenharia"},
        )
        self.assertEqual(out.status_code, 200)
        self.assertEqual(out.json()["status"], "planejado")
        self.assertFalse(out.json()["modelo_ou_ferramenta_executados"])

    def test_default_execution_is_disabled_and_not_fabricated(self):
        # API chama o motor, mas a configuracao default nao provisiona modelos.
        with patch.object(self.runtime.agent_agency, "enabled", False):
            out = self.client.post(
                "/api/agencia/executar", headers=self._headers(),
                json={"objetivo": "Testar", "aprovado": True},
            )
        self.assertEqual(out.status_code, 200)
        self.assertEqual(out.json()["status"], "desabilitado")
        self.assertFalse(out.json()["executado"])


if __name__ == "__main__":
    unittest.main()
