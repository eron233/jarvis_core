"""Testes unitarios para o motor de modelagem de ameaca do JARVIS."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import SystemLoopConfig, bootstrap_runtime
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.system_config import JarvisEnvironmentConfig
from security.threat_model_engine import ThreatModelEngine


def make_threat_artifact_path(name: str, suffix: str) -> Path:
    """Retorna o path de artefato usado nos cenarios de ameaca."""

    return PROJECT_ROOT / "tests" / "_cloud_artifacts" / "threat_model" / f"{name}_{suffix}.json"


def reset_path(path: Path) -> None:
    """Limpa um artefato persistente antes da execucao do teste."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class ThreatModelEngineTests(unittest.TestCase):
    """Valida cobertura, risco e resumo do motor de ameaca interno."""

    def build_state(self, name: str = "threat") -> tuple[dict, dict, dict]:
        """Monta estado, healthcheck e ambiente para os cenarios de ameaca."""

        queue_path = make_threat_artifact_path(name, "queue")
        semantic_path = make_threat_artifact_path(name, "semantic")
        goal_path = make_threat_artifact_path(name, "goals")

        for path in (queue_path, semantic_path, goal_path):
            reset_path(path)

        runtime, _ = bootstrap_runtime(
            runtime=InternalAgentRuntime(),
            config=SystemLoopConfig(
                queue_storage_path=queue_path,
                semantic_storage_path=semantic_path,
                goal_storage_path=goal_path,
                install_signal_handlers=False,
            ),
            logger=lambda _message: None,
        )

        runtime_state = runtime.describe_state()
        health_report = runtime.build_health_report(
            api_started_at="2026-03-13T00:00:00+00:00",
            token_configurado=True,
            dispositivo_confiavel_configurado=True,
        )
        environment_report = JarvisEnvironmentConfig(
            env="production",
            token="token-seguro",
            trusted_device_id="eron-celular-principal",
            data_dir=queue_path.parent,
            logs_dir=queue_path.parent / "logs",
            reports_dir=queue_path.parent / "reports",
            queue_storage_path=queue_path,
            semantic_storage_path=semantic_path,
            goals_storage_path=goal_path,
        ).build_environment_report()
        return runtime_state, health_report, environment_report

    def test_build_threat_model_covers_core_assets_and_surfaces(self) -> None:
        """Confirma inventario de ativos e superficies esperados no modelo."""

        runtime_state, health_report, environment_report = self.build_state("coverage")
        engine = ThreatModelEngine()

        model = engine.build_threat_model(
            runtime_state=runtime_state,
            health_report=health_report,
            environment_report=environment_report,
        )

        asset_ids = {asset["asset_id"] for asset in model["inventario_de_ativos"]}
        surface_ids = {surface["surface_id"] for surface in model["mapa_de_superficies"]}

        self.assertTrue(
            {
                "semantic_memory",
                "task_queue",
                "audit_log",
                "api_service",
                "dashboard",
                "environment_config",
                "access_token",
                "trusted_device",
                "goal_state",
                "runtime_state",
            }.issubset(asset_ids)
        )
        self.assertTrue(
            {
                "api_http",
                "dashboard_web",
                "persisted_files",
                "environment_variables",
                "startup_shutdown",
                "docker_volumes",
                "operational_logs",
                "authentication_gate",
            }.issubset(surface_ids)
        )

    def test_risk_classification_escalates_when_authentication_is_not_configured(self) -> None:
        """Verifica escalonamento de risco quando autenticacao esta incompleta."""

        runtime_state, health_report, environment_report = self.build_state("auth_risk")
        engine = ThreatModelEngine()

        insecure_environment = {
            **environment_report,
            "autenticacao_configurada": {
                "token_configurado": False,
                "dispositivo_confiavel_configurado": False,
            },
        }
        insecure_health = {
            **health_report,
            "configuracao_minima_valida": False,
        }

        risks = engine.classify_risks(
            runtime_state=runtime_state,
            health_report=insecure_health,
            environment_report=insecure_environment,
        )
        risks_by_asset = {risk["asset_id"]: risk for risk in risks}

        self.assertEqual(risks_by_asset["access_token"]["nivel_risco"], "critico")
        self.assertIn(risks_by_asset["trusted_device"]["nivel_risco"], {"alto", "critico"})
        self.assertIn(risks_by_asset["api_service"]["nivel_risco"], {"alto", "critico"})

    def test_dependency_map_and_summary_are_generated_in_ptbr(self) -> None:
        """Confirma mapa de dependencias e resumo localizados em pt-BR."""

        runtime_state, health_report, environment_report = self.build_state("summary")
        engine = ThreatModelEngine()

        dependencies = engine.build_dependency_map(
            runtime_state=runtime_state,
            health_report=health_report,
        )
        model = engine.build_threat_model(
            runtime_state=runtime_state,
            health_report=health_report,
            environment_report=environment_report,
        )

        dependency_ids = {dependency["dependency_id"] for dependency in dependencies}
        self.assertEqual(
            dependency_ids,
            {"runtime", "planner", "queue", "memory", "api", "authentication", "persistence"},
        )
        self.assertEqual(model["mensagem"], "Modelo de ameaca interno do JARVIS gerado com sucesso.")
        self.assertIn(model["resumo_ptbr"]["risco_geral"], {"baixo", "medio", "alto", "critico"})
        self.assertEqual(model["resumo_ptbr"]["total_ativos"], 10)
        self.assertEqual(model["resumo_ptbr"]["total_superficies"], 8)


if __name__ == "__main__":
    unittest.main()
