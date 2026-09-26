"""Testes de que a proposta de patch nao afirma alteracoes que nao fez."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security.git_branch_patcher import GitBranchPatcherEngine


class GitPatchProposalTests(unittest.TestCase):
    """O motor verifica um patch proposto; nao cria branch nem altera arquivos."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.projeto = self.tmp / "projeto"
        self.projeto.mkdir()
        self.alvo = self.projeto / "modulo.py"
        self.alvo.write_text("def antigo():\n    return 1\n", encoding="utf-8")
        self.engine = GitBranchPatcherEngine(project_root=self.projeto, data_dir=self.tmp / "relatorios")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def propor(self, conteudo: str = "def novo():\n    return 2\n") -> dict:
        """Submete uma proposta de patch para o arquivo alvo."""

        return self.engine.prepare_patch_for_review(
            vulnerability_id="VULN-001",
            target_filepath="modulo.py",
            patch_content=conteudo,
        )

    def test_nao_altera_o_arquivo_alvo(self) -> None:
        """
        A docstring dizia que a modificacao era aplicada. O arquivo nunca era
        escrito: o conteudo original era lido e descartado.
        """

        self.propor()

        self.assertEqual(self.alvo.read_text(encoding="utf-8"), "def antigo():\n    return 1\n")

    def test_declara_que_nao_criou_branch_nem_aplicou_o_patch(self) -> None:
        """Nenhum comando git era executado, mas o relatorio nomeava uma branch."""

        relatorio = self.propor()

        self.assertFalse(relatorio["branch_criada"])
        self.assertFalse(relatorio["patch_aplicado"])
        self.assertEqual(relatorio["nome_branch_sugerida"], "jarvis/fix-vuln-001")

    def test_nao_afirma_que_os_testes_passaram(self) -> None:
        """
        O relatorio trazia `testes_passaram` verdadeiro e o resumo dizia
        "Testes: APROVADO", enquanto `run_tests` era ignorado por completo.
        """

        relatorio = self.propor()

        self.assertFalse(relatorio["testes_executados"])
        self.assertTrue(relatorio["testes_solicitados"])
        self.assertIn("nao esta implementada", relatorio["motivo_testes"])
        self.assertNotIn("APROVADO", relatorio["resumo_ptbr"])

    def test_produz_um_diff_real_entre_o_arquivo_e_a_proposta(self) -> None:
        """O diff era um texto fixo que nao comparava nada."""

        diff = self.propor()["diff_unificado"]

        self.assertIn("-def antigo():", diff)
        self.assertIn("+def novo():", diff)
        self.assertIn("--- a/modulo.py", diff)

    def test_patch_com_erro_de_sintaxe_e_reprovado(self) -> None:
        """A verificacao de sintaxe, que e a parte real, precisa continuar valendo."""

        relatorio = self.propor("def quebrado(:\n")

        self.assertFalse(relatorio["sintaxe_valida"])
        self.assertEqual(relatorio["status_patch"], "erro_de_sintaxe")

    def test_nome_antigo_continua_funcionando(self) -> None:
        """O nome anterior segue disponivel para nao quebrar chamadores externos."""

        relatorio = self.engine.apply_patch_in_isolated_branch(
            vulnerability_id="VULN-002",
            target_filepath="modulo.py",
            patch_content="x = 1\n",
        )

        self.assertFalse(relatorio["branch_criada"])


if __name__ == "__main__":
    unittest.main()
