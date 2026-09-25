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

        # Sem sintetizador instalado a resposta e honesta: nada de WAV vazio com "sucesso".
        self.assertIn(res["status"], {"sucesso", "indisponivel"})
        if res["status"] == "sucesso":
            self.assertTrue(Path(res["arquivo_audio"]).exists())
            self.assertGreater(Path(res["arquivo_audio"]).stat().st_size, 44)
        else:
            self.assertIn("motivo", res)

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
        # Offline nunca inventa fonte ficticia.
        if res.get("status") == "indisponivel":
            self.assertEqual(res["fontes"], [])
        for fonte in res["fontes"]:
            self.assertNotIn("pesquisa.local", fonte["url"])

    def test_web_browser_bloqueia_rede_interna(self) -> None:
        browser = WebBrowserEngine()
        for url in ("http://127.0.0.1:8000/health", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd"):
            with self.subTest(url=url):
                res = browser.fetch_page_content(url)
                self.assertEqual(res["status"], "bloqueado")

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
        self.assertTrue(tick["simulado"])
        self.assertIn("SIMULADOS", tick["aviso"])

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
