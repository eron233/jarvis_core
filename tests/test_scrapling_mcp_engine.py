"""Testes do ScraplingMCPEngine - conteudo real via injecao, sem rede."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.scrapling_mcp_engine import ScraplingMCPEngine


class _FakeBrowserEngineFalha:
    """Dublê de WebBrowserEngine que sempre falha, sem tocar a rede."""

    def fetch_page_content(self, url, html_content=None):  # noqa: ANN001
        return {"status": "erro", "offline": True, "motivo": "host inalcancavel (simulado)"}


class ScraplingMCPEngineTests(unittest.TestCase):
    """Valida que o conteudo retornado pelo motor stealth MCP e real."""

    def setUp(self) -> None:
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="scrapling_mcp_test_"))
        self.engine = ScraplingMCPEngine(data_dir=self._tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_scrape_stealth_com_html_injetado_retorna_texto_real(self) -> None:
        html_falso = """
        <html>
          <head><title>Pagina Stealth</title></head>
          <body>
            <script>alert('nao deveria aparecer');</script>
            <h1>Conteudo Verdadeiro da Pagina</h1>
            <p>Este texto foi realmente extraido do HTML injetado.</p>
          </body>
        </html>
        """

        resultado = self.engine.scrape_stealth_mcp(
            "https://alvo.example/pagina",
            html_content=html_falso,
        )

        self.assertFalse(resultado["is_error"])
        texto_principal = resultado["content"][0]["text"]
        self.assertIn("Conteudo Verdadeiro da Pagina", texto_principal)
        self.assertIn("realmente extraido do HTML injetado", texto_principal)
        self.assertNotIn("alert(", texto_principal)

        recurso = resultado["content"][1]["resource"]
        self.assertEqual(recurso["uri"], "https://alvo.example/pagina")
        self.assertIn("Conteudo Verdadeiro da Pagina", recurso["text"])

        # Estrutura MCP mantida
        self.assertEqual(resultado["mcp_protocol_version"], "2024-11-05")
        self.assertEqual(resultado["tool_call"], "scrapling_fetch_page")

    def test_scrape_stealth_erro_com_engine_injetado_nao_toca_rede(self) -> None:
        resultado = self.engine.scrape_stealth_mcp(
            "http://url-invalida.exemplo.invalido",
            browser_engine=_FakeBrowserEngineFalha(),
        )

        self.assertTrue(resultado["is_error"])
        self.assertIn("host inalcancavel", resultado["content"][0]["text"])
        self.assertEqual(len(resultado["content"]), 1)


if __name__ == "__main__":
    unittest.main()
