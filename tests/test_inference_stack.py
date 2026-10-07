"""Testes do ponto 6: inferência local e roteamento de modelos."""

from pathlib import Path
import tempfile
import unittest

from runtime.corporate_agent_hierarchy import CorporateAgentHierarchyEngine
from runtime.inference_stack import (
    InferenceStackConfig,
    LocalInferenceRouter,
    validate_inference_endpoint,
)
from runtime.internal_agent_runtime import InternalAgentRuntime


class _FakeBackend:
    def __init__(self, name: str, status: str = "sucesso") -> None:
        self.name = name
        self.status = status
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.status != "sucesso":
            return {
                "status": "indisponivel",
                "provider": self.name,
                "modelo": kwargs["model"],
                "motivo": "backend indisponível",
            }
        return {
            "status": "sucesso",
            "provider": self.name,
            "modelo": kwargs["model"],
            "conteudo": "resposta real do backend de teste",
            "tool_calls": [],
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "latencia_ms": 25.0,
            "tokens_por_segundo_estimado": 200.0,
        }

    def list_models(self):
        return {
            "status": self.status,
            "provider": self.name,
            "modelos": ["modelo-teste"] if self.status == "sucesso" else [],
        }


class InferenceConfigTests(unittest.TestCase):
    def test_defaults_keep_inference_and_model_selection_disabled(self):
        config = InferenceStackConfig.from_env({})
        self.assertFalse(config.enabled)
        self.assertEqual(config.provider_order, ("llamacpp", "ollama"))
        self.assertIsNone(config.model_light)
        self.assertIsNone(config.model_heavy)
        self.assertIsNone(config.model_general)
        self.assertFalse(config.allow_remote_endpoints)

    def test_remote_endpoint_is_blocked_by_default(self):
        self.assertIsNone(
            validate_inference_endpoint("http://127.0.0.1:8080/v1")
        )
        self.assertIsNotNone(
            validate_inference_endpoint("https://example.com/v1")
        )

    def test_alias_resolution_prefers_capability_then_tier_then_general(self):
        config = InferenceStackConfig(
            enabled=True,
            model_light="modelo-leve",
            model_heavy="modelo-pesado",
            model_general="modelo-geral",
            model_coding="modelo-codigo",
        )
        router = LocalInferenceRouter(config)

        coding = router.resolve_model(tier="heavy", capability="coding")
        self.assertEqual(coding["modelo"], "modelo-codigo")
        self.assertEqual(coding["origem"], "alias:coding")

        reasoning = router.resolve_model(tier="heavy", capability="reasoning")
        self.assertEqual(reasoning["modelo"], "modelo-pesado")
        self.assertEqual(reasoning["origem"], "alias:heavy")

        general = router.resolve_model(tier="unknown")
        self.assertEqual(general["modelo"], "modelo-geral")
        self.assertEqual(general["origem"], "alias:general")

    def test_no_model_alias_returns_unavailable_not_fake_model(self):
        router = LocalInferenceRouter(InferenceStackConfig(enabled=True))
        result = router.resolve_model(tier="heavy", capability="coding")
        self.assertEqual(result["status"], "indisponivel")
        self.assertIsNone(result["modelo"])
        self.assertIn("benchmark local", result["motivo"])


class InferenceRouterTests(unittest.TestCase):
    def test_router_falls_back_between_real_backends(self):
        config = InferenceStackConfig(
            enabled=True,
            provider_order=("llamacpp", "ollama"),
            model_general="modelo-teste",
        )
        router = LocalInferenceRouter(config)
        first = _FakeBackend("llamacpp", status="indisponivel")
        second = _FakeBackend("ollama", status="sucesso")
        router.backends = {
            "llamacpp": first,
            "ollama": second,
        }

        result = router.chat(
            [{"role": "user", "content": "Olá"}],
            tier="general",
        )

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(result["modelo"], "modelo-teste")
        self.assertEqual(len(result["roteamento"]["attempts"]), 2)
        self.assertEqual(first.calls[0]["model"], "modelo-teste")
        self.assertEqual(second.calls[0]["model"], "modelo-teste")

    def test_benchmark_reports_measured_runtime_without_claiming_quality(self):
        config = InferenceStackConfig(
            enabled=True,
            provider_order=("llamacpp",),
            model_general="modelo-teste",
        )
        router = LocalInferenceRouter(config)
        router.backends = {"llamacpp": _FakeBackend("llamacpp", status="sucesso")}

        result = router.benchmark_model(
            ["Diga olá.", "Resuma 2+2."],
            repetitions=2,
            tier="general",
        )

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["total_execucoes"], 4)
        self.assertEqual(result["sucessos"], 4)
        self.assertEqual(result["falhas"], 0)
        self.assertEqual(result["latencia_media_ms"], 25.0)
        self.assertEqual(result["tokens_por_segundo_medio"], 200.0)
        self.assertIn("Qualidade", result["observacao"])

    def test_disabled_router_does_not_call_backend(self):
        router = LocalInferenceRouter(
            InferenceStackConfig(
                enabled=False,
                model_general="modelo-teste",
            )
        )
        fake = _FakeBackend("llamacpp")
        router.backends = {"llamacpp": fake}

        result = router.chat([{"role": "user", "content": "Olá"}])

        self.assertEqual(result["status"], "indisponivel")
        self.assertEqual(fake.calls, [])


class CorporateRoutingIntegrationTests(unittest.TestCase):
    def test_hierarchy_has_no_fictional_hardcoded_model_names(self):
        config = InferenceStackConfig(
            enabled=True,
            model_light="modelo-leve-real",
            model_heavy="modelo-pesado-real",
            model_coding="modelo-codigo-real",
        )
        router = LocalInferenceRouter(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            hierarchy = CorporateAgentHierarchyEngine(
                data_dir=Path(temp_dir),
                inference_router=router,
            )
            report = hierarchy.dispatch_corporate_task(
                department="Engenharia",
                task_title="Refatorar módulo",
                task_payload={"arquivo": "runtime/x.py"},
                task_complexity="critica",
            )

        self.assertEqual(report["roteamento_modelo"]["tier"], "pesado")
        self.assertEqual(
            report["roteamento_modelo"]["modelo_selecionado"],
            "modelo-codigo-real",
        )
        self.assertTrue(report["roteamento_modelo"]["modelo_resolvido"])
        self.assertFalse(hierarchy.get_hierarchy_status()["modelos_hardcoded"])

    def test_runtime_exposes_inference_router(self):
        runtime = InternalAgentRuntime()
        runtime.bootstrap()
        self.assertTrue(hasattr(runtime, "inference_router"))
        self.assertIs(
            runtime.corporate_hierarchy_engine.inference_router,
            runtime.inference_router,
        )


if __name__ == "__main__":
    unittest.main()
