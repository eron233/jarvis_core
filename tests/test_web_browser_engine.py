"""Testes do WebBrowserEngine - parsing real de HTML injetado, sem rede."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.web_browser_engine import WebBrowserEngine


class WebBrowserEngineTests(unittest.TestCase):
    """Valida a extração real de conteúdo a partir de HTML injetado (sem tocar a rede)."""

    def setUp(self) -> None:
        self.engine = WebBrowserEngine(user_agent="TesteJarvis/1.0")

    def test_fetch_page_content_limpa_scripts_e_estilos(self) -> None:
        html_falso = """
        <html>
          <head>
            <title>Pagina de Teste</title>
            <style>body { color: red; }</style>
            <script>console.log('nao deveria aparecer no texto');</script>
          </head>
          <body>
            <h1>Titulo Principal</h1>
            <p>Este e um paragrafo real com conteudo util.</p>
            <script>var x = 1;</script>
          </body>
        </html>
        """

        resultado = self.engine.fetch_page_content("https://exemplo.local/pagina", html_content=html_falso)

        self.assertEqual(resultado["status"], "sucesso")
        self.assertFalse(resultado["baixado_via_rede"])
        self.assertIn("Titulo Principal", resultado["conteudo_texto_limpo"])
        self.assertIn("paragrafo real com conteudo util", resultado["conteudo_texto_limpo"])
        # Conteudo de script/style nao deve vazar para o texto limpo
        self.assertNotIn("console.log", resultado["conteudo_texto_limpo"])
        self.assertNotIn("color: red", resultado["conteudo_texto_limpo"])
        self.assertNotIn("<h1>", resultado["conteudo_texto_limpo"])
        self.assertGreater(resultado["tamanho_texto_chars"], 0)

    def test_fetch_page_content_erro_e_honesto(self) -> None:
        # Sem html_content injetado, uma URL invalida deve falhar de verdade
        # (sem fabricar conteudo) e sinalizar o erro claramente.
        resultado = self.engine.fetch_page_content("http://dominio-que-nao-existe.invalido.local/xyz")

        self.assertEqual(resultado["status"], "erro")
        self.assertTrue(resultado.get("offline"))
        self.assertEqual(resultado["conteudo_texto_limpo"], "")
        self.assertIn("motivo", resultado)

    def test_search_and_extract_com_resultados_injetados(self) -> None:
        html_resultados = """
        <html><body>
        <div class="result">
          <a rel="nofollow" class="result__a" href="https://site-um.example/artigo">Resultado Um Sobre o Tema</a>
          <a class="result__snippet" href="https://site-um.example/artigo">Trecho real do primeiro resultado sobre o tema pesquisado.</a>
        </div>
        <div class="result">
          <a rel="nofollow" class="result__a" href="https://site-dois.example/pagina">Resultado Dois Relacionado</a>
          <a class="result__snippet" href="https://site-dois.example/pagina">Outro trecho real, com informacoes diferentes.</a>
        </div>
        </body></html>
        """

        resultado = self.engine.search_and_extract("tema pesquisado", max_results=3, html_content=html_resultados)

        self.assertEqual(resultado["status"], "sucesso")
        self.assertEqual(resultado["total_fontes_encontradas"], 2)
        self.assertEqual(resultado["fontes"][0]["url"], "https://site-um.example/artigo")
        self.assertEqual(resultado["fontes"][0]["titulo"], "Resultado Um Sobre o Tema")
        self.assertIn("Trecho real do primeiro resultado", resultado["fontes"][0]["resumo_snippet"])
        self.assertEqual(resultado["fontes"][1]["titulo"], "Resultado Dois Relacionado")

    def test_search_and_extract_decodifica_redirecionamento_duckduckgo(self) -> None:
        html_resultados = """
        <html><body>
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdestino-real.example%2Fpagina&amp;rut=1">Titulo Redirecionado</a>
        <a class="result__snippet" href="#">Trecho do resultado redirecionado.</a>
        </body></html>
        """

        resultado = self.engine.search_and_extract("consulta", max_results=1, html_content=html_resultados)

        self.assertEqual(resultado["fontes"][0]["url"], "https://destino-real.example/pagina")

    def test_search_and_extract_sem_resultados_e_honesto(self) -> None:
        resultado = self.engine.search_and_extract("nada aqui", max_results=3, html_content="<html><body></body></html>")

        self.assertEqual(resultado["status"], "sucesso")
        self.assertEqual(resultado["total_fontes_encontradas"], 0)
        self.assertEqual(resultado["fontes"], [])


if __name__ == "__main__":
    unittest.main()
