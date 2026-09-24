"""
Testes unitários abrangentes cobrindo a implementação e integração dos 6 Módulos Especializados do JARVIS.
"""

from pathlib import Path
import tempfile
import unittest

from device.device_profiler import DeviceProfiler
from learning.research_knowledge_engine import ResearchKnowledgeEngine
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.tool_developer_engine import ToolDeveloperEngine
from security.auto_evolution_engine import AutoEvolutionEngine
from workers.worker_creative_studio import CreativeStudioWorker
from workers.worker_market_analysis import MarketAnalysisWorker


class AllSixModulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_modulo_1_auto_evolution_engine(self) -> None:
        state_path = self.tmp_path / "evolution_state.json"
        engine = AutoEvolutionEngine(state_path=state_path)
        report = engine.run_evolution_cycle()

        self.assertIn("vulnerabilidades_encontradas", report)
        self.assertIn("status_evolucao", report)
        self.assertTrue(state_path.exists())

    def test_modulo_2_tool_developer_engine(self) -> None:
        tools_dir = self.tmp_path / "tools"
        engine = ToolDeveloperEngine(tools_dir=tools_dir)

        tool = engine.develop_tool(
            tool_name="Custom Ping Tool",
            purpose="Mede latencia de rede",
            code_body="pass",
            domain="infra",
        )

        self.assertTrue(tool["validada"])
        tools = engine.list_developed_tools()
        self.assertEqual(len(tools), 1)

    def test_modulo_3_research_knowledge_engine(self) -> None:
        knowledge_dir = self.tmp_path / "knowledge"
        engine = ResearchKnowledgeEngine(knowledge_dir=knowledge_dir)

        item = engine.ingest_source(
            title="Livro de Arquitetura",
            source_type="livro",
            raw_text="Princípio 1: Determinismo.\nPrincípio 2: Resiliência.",
            topics=["arquitetura"],
        )

        self.assertIn("taxa_compressao_pct", item)
        search_res = engine.search_knowledge("Determinismo")
        self.assertEqual(len(search_res), 1)

    def test_modulo_4_market_analysis_worker(self) -> None:
        market_dir = self.tmp_path / "market"
        worker = MarketAnalysisWorker(data_dir=market_dir)

        report = worker.analyze_market_session(
            asset="WDO",
            price_history=[{"price": 5.20}, {"price": 5.25}],
            flow_data=[{"side": "buy", "volume": 1000}, {"side": "sell", "volume": 500}],
            news_events=[{"timestamp": "09:00", "titulo": "Abertura de Mercado"}],
        )

        self.assertEqual(report["metricas_fluxo"]["bias"], "comprador")
        self.assertEqual(report["metricas_preco"]["amplitude"], 0.05)

    def test_modulo_5_creative_studio_worker(self) -> None:
        studio_dir = self.tmp_path / "studio"
        worker = CreativeStudioWorker(studio_dir=studio_dir)

        project = worker.incubate_project(
            project_name="Plataforma X",
            concept="Sistema de automação",
            target_market="PMEs",
            competitors=[{"nome": "CompA", "falhas": ["Instabilidade"]}],
        )

        self.assertEqual(project["projeto"], "Plataforma X")
        self.assertEqual(len(project["analise_concorrencia"]), 1)

    def test_modulo_6_device_profiler(self) -> None:
        profiler_dir = self.tmp_path / "profiler"
        profiler = DeviceProfiler(profiler_dir=profiler_dir)

        profile = profiler.analyze_device_and_profile(
            installed_apps=["GameA", "Discord"],
            observed_usages=["Jogos"],
        )

        self.assertIn("hardware", profile)
        self.assertIn("otimizacoes_simuladas", profile)
        self.assertEqual(profile["status_simulacao"], "simulado_com_sucesso")

    def test_runtime_integration_of_all_six_modules(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "auto_evolution_engine"))
        self.assertTrue(hasattr(runtime, "tool_developer_engine"))
        self.assertTrue(hasattr(runtime, "research_knowledge_engine"))
        self.assertTrue(hasattr(runtime, "market_analysis_worker"))
        self.assertTrue(hasattr(runtime, "creative_studio_worker"))
        self.assertTrue(hasattr(runtime, "device_profiler"))


if __name__ == "__main__":
    unittest.main()
