"""Regressoes de seguranca do cadastro de ferramentas geradas pelo JARVIS."""

from pathlib import Path
import tempfile
import unittest

from runtime.tool_developer_engine import ToolDeveloperEngine


class ToolDeveloperSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = ToolDeveloperEngine(tools_dir=self.root / "tools")

    def tearDown(self):
        self.temp.cleanup()

    def test_cadastra_sem_executar_codigo_recebido(self):
        marcador = self.root / "executou.txt"
        proposito = (
            'texto"""\nfrom pathlib import Path\n'
            f'Path({str(marcador)!r}).write_text("EXECUTOU")\n'
            '"""'
        )
        resultado = self.engine.develop_tool(
            "Ferramenta Segura", proposito, "return {'status': 'ok'}"
        )
        self.assertTrue(resultado["validada"])
        self.assertTrue(resultado["sintaxe_valida"])
        self.assertFalse(resultado["codigo_executado"])
        self.assertFalse(resultado["isolamento_validado"])
        self.assertFalse(marcador.exists())
        codigo = Path(resultado["file_path"]).read_text(encoding="utf-8")
        self.assertIn("TOOL_METADATA", codigo)
        self.assertIn("def run_tool(", codigo)

    def test_recusa_path_traversal_em_nome(self):
        for nome in ("../escape", "../../escape", "pasta/ferramenta", "pasta\\ferramenta", "", "."):
            with self.subTest(nome=nome):
                resultado = self.engine.develop_tool(nome, "teste", "pass")
                self.assertEqual(resultado["status"], "nome_invalido")
                self.assertFalse(resultado["validada"])
        self.assertEqual(self.engine.list_developed_tools(), [])
        self.assertFalse((self.root / "escape.py").exists())

    def test_codigo_invalido_nao_e_gravado(self):
        resultado = self.engine.develop_tool("InvalidTool", "teste", "if True print('erro')")
        self.assertFalse(resultado["validada"])
        self.assertFalse((self.root / "tools" / "invalidtool.py").exists())

    def test_nao_inventa_sucesso_sem_retorno(self):
        resultado = self.engine.develop_tool("NoReturn", "teste", "valor = 2 + 2")
        self.assertTrue(resultado["validada"])
        codigo = Path(resultado["file_path"]).read_text(encoding="utf-8")
        self.assertIn("'status': 'sem_resultado'", codigo)
        self.assertNotIn("'status': 'sucesso'", codigo)

    def test_execucao_gerada_e_bloqueada_sem_isolamento_forte(self):
        resultado = self.engine.develop_tool(
            "Teste", "nao executar", "return {'status': 'sucesso'}"
        )
        self.assertTrue(resultado["validada"])
        saida = self.engine.execute_tool_in_sandbox("Teste", params={"a": 1})
        self.assertEqual(saida["status"], "bloqueado_por_seguranca")
        self.assertFalse(saida["executado"])
        self.assertFalse(saida["isolamento_validado"])

    def test_ferramenta_inexistente_nao_executa(self):
        saida = self.engine.execute_tool_in_sandbox("Desconhecida")
        self.assertEqual(saida["status"], "erro")
        self.assertFalse(saida["executado"])


if __name__ == "__main__":
    unittest.main()
