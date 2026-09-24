"""
Testes unitários abrangentes cobrindo voz local, automação de SO, pesquisa web, extrator universal de arquivos e feed de mercado.
"""

from pathlib import Path
import tempfile
import unittest

from learning.universal_file_extractor import UniversalFileExtractor
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.system_automation import SystemAutomationEngine
from runtime.voice_engine import LocalVoiceEngine
from runtime.web_browser_engine import WebBrowserEngine
from workers.market_websocket_feed import MarketWebSocketFeed


class VoiceAutomationUniversalIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_local_voice_engine(self) -> None:
        voice = LocalVoiceEngine(audio_dir=self.tmp_path / "audio")
        res = voice.speak("Testando a voz do Jarvis")

        self.assertEqual(res["status"], "sucesso")
        self.assertTrue(Path(res["arquivo_audio"]).exists())

    def test_system_automation_engine(self) -> None:
        auto = SystemAutomationEngine()
        metrics = auto.get_system_metrics()
        self.assertIn("cpus_logicos", metrics)

        launch_res = auto.launch_application("rm -rf /")
        self.assertEqual(launch_res["status"], "bloqueado")

    def test_web_browser_engine(self) -> None:
        browser = WebBrowserEngine()
        res = browser.search_and_extract("Jarvis AI")
        self.assertIn("fontes", res)

    def test_universal_file_extractor(self) -> None:
        extractor = UniversalFileExtractor()

        # Teste com TXT
        txt_file = self.tmp_path / "sample.txt"
        txt_file.write_text("Conteúdo de teste para extração universal.", encoding="utf-8")
        res_txt = extractor.extract_and_ingest_file(txt_file)
        self.assertEqual(res_txt["status"], "sucesso")

        # Teste com JSON
        json_file = self.tmp_path / "data.json"
        json_file.write_text('{"chave": "valor"}', encoding="utf-8")
        res_json = extractor.extract_and_ingest_file(json_file)
        self.assertEqual(res_json["status"], "sucesso")

    def test_market_websocket_feed(self) -> None:
        feed = MarketWebSocketFeed(asset="WDO")
        tick = feed.fetch_live_tick()
        self.assertEqual(tick["ativo"], "WDO")
        self.assertIn("preco_atual", tick)

    def test_runtime_integration_of_new_engines(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "voice_engine"))
        self.assertTrue(hasattr(runtime, "system_automation_engine"))
        self.assertTrue(hasattr(runtime, "web_browser_engine"))
        self.assertTrue(hasattr(runtime, "universal_file_extractor"))
        self.assertTrue(hasattr(runtime, "market_websocket_feed"))


if __name__ == "__main__":
    unittest.main()
