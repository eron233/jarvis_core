"""Testes do ScrapeGraphEngine - extracao estruturada real a partir de HTML."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from learning.scrapegraph_engine import ScrapeGraphEngine


class ScrapeGraphEngineTests(unittest.TestCase):
    """Valida que a extracao por grafo reflete o conteudo real do HTML."""

    def setUp(self) -> None:
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="scrapegraph_test_"))
        self.engine = ScrapeGraphEngine(data_dir=self._tmp_dir)

        self.html = """
        <html>
          <head><title>Loja de Produtos Reais</title></head>
          <body>
            <h1>Catalogo de Ofertas</h1>
            <ul>
              <li>Produto Alfa</li>
              <li>Produto Beta</li>
              <li>Produto Gama</li>
            </ul>
            <p>Preco principal: R$ 29.99 com desconto de 10,50 reais.</p>
            <p>Preco secundario: 149,90</p>
          </body>
        </html>
        """

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_extrai_titulo_real(self) -> None:
        schema = {"titulo": "str"}
        resultado = self.engine.extract_structured_graph("https://loja.example/produtos", self.html, schema)

        self.assertEqual(resultado["dados_estruturados_extraidos"]["titulo"], "Catalogo de Ofertas")

    def test_extrai_lista_de_itens_real(self) -> None:
        schema = {"itens": "list[str]"}
        resultado = self.engine.extract_structured_graph("https://loja.example/produtos", self.html, schema)

        itens = resultado["dados_estruturados_extraidos"]["itens"]
        self.assertEqual(itens, ["Produto Alfa", "Produto Beta", "Produto Gama"])

    def test_extrai_numeros_reais(self) -> None:
        schema = {"precos": "list[float]", "preco_principal": "float"}
        resultado = self.engine.extract_structured_graph("https://loja.example/produtos", self.html, schema)

        dados = resultado["dados_estruturados_extraidos"]
        self.assertIn(29.99, dados["precos"])
        self.assertIn(10.50, dados["precos"])
        self.assertIn(149.90, dados["precos"])
        self.assertEqual(dados["preco_principal"], 29.99)

    def test_campo_sem_correspondencia_retorna_honesto(self) -> None:
        html_vazio = "<html><body><p>Sem listas nem numeros aqui.</p></body></html>"
        schema = {"itens_inexistentes": "list[str]", "preco_inexistente": "float"}
        resultado = self.engine.extract_structured_graph("https://vazio.example", html_vazio, schema)

        dados = resultado["dados_estruturados_extraidos"]
        self.assertEqual(dados["itens_inexistentes"], [])
        self.assertIsNone(dados["preco_inexistente"])

    def test_grafo_reflete_campos_do_schema(self) -> None:
        schema = {"titulo": "str", "itens": "list[str]"}
        resultado = self.engine.extract_structured_graph("https://loja.example/produtos", self.html, schema)

        node_ids = {node["id"] for node in resultado["grafo_extracao"]["nos"]}
        self.assertIn("node_root", node_ids)
        self.assertIn("node_titulo", node_ids)
        self.assertIn("node_itens", node_ids)

        arestas_origens = {edge["origem"] for edge in resultado["grafo_extracao"]["arestas"]}
        self.assertEqual(arestas_origens, {"node_root"})


if __name__ == "__main__":
    unittest.main()
