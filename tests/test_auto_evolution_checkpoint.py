"""Testes do checkpoint e do rollback do motor de autoevolucao."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import security.auto_evolution_engine as auto_evolution
from security.auto_evolution_engine import AutoEvolutionEngine


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Executa um comando git dentro do repositorio de teste."""

    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=False)


class AutoEvolutionCheckpointTests(unittest.TestCase):
    """O checkpoint precisa existir de verdade e o rollback nao pode apagar trabalho alheio."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "teste@jarvis.local")
        git(self.repo, "config", "user.name", "Teste")
        (self.repo / "arquivo.txt").write_text("estado_commitado", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "inicial")

        self.patcher = patch.object(auto_evolution, "PROJECT_ROOT", self.repo)
        self.patcher.start()
        self.engine = AutoEvolutionEngine(state_path=self.tmp / "estado.json")

    def tearDown(self) -> None:
        self.patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_checkpoint_guarda_o_commit_do_estado_atual(self) -> None:
        """
        `git stash create` monta um commit e devolve o identificador, mas nao o
        registra em lugar nenhum. Descartar a saida equivalia a nao ter checkpoint.
        """

        (self.repo / "arquivo.txt").write_text("trabalho_em_andamento", encoding="utf-8")

        checkpoint = self.engine._create_state_checkpoint()

        self.assertTrue(checkpoint["disponivel"])
        self.assertIsNotNone(checkpoint["commit"])
        self.assertEqual(git(self.repo, "cat-file", "-t", checkpoint["commit"]).stdout.strip(), "commit")

    def test_rollback_preserva_trabalho_nao_commitado_do_dono(self) -> None:
        """
        O rollback anterior era `git checkout -- .` incondicional, que descartava
        qualquer alteracao presente na arvore, inclusive a que nao veio do ciclo.
        """

        alvo = self.repo / "arquivo.txt"
        alvo.write_text("trabalho_do_dono", encoding="utf-8")
        checkpoint = self.engine._create_state_checkpoint()

        # O ciclo de evolucao altera o mesmo arquivo.
        alvo.write_text("alteracao_da_evolucao", encoding="utf-8")

        self.assertTrue(self.engine._rollback_to_checkpoint(checkpoint))
        self.assertEqual(alvo.read_text(encoding="utf-8"), "trabalho_do_dono")

    def test_rollback_desfaz_a_alteracao_quando_a_arvore_estava_limpa(self) -> None:
        """Com a arvore limpa no checkpoint, tudo que mudou depois e do ciclo."""

        checkpoint = self.engine._create_state_checkpoint()
        self.assertTrue(checkpoint["arvore_limpa"])

        (self.repo / "arquivo.txt").write_text("alteracao_da_evolucao", encoding="utf-8")

        self.assertTrue(self.engine._rollback_to_checkpoint(checkpoint))
        self.assertEqual((self.repo / "arquivo.txt").read_text(encoding="utf-8"), "estado_commitado")

    def test_sem_checkpoint_utilizavel_nada_e_revertido(self) -> None:
        """Falhar em registrar o checkpoint nao pode virar licenca para apagar a arvore."""

        alvo = self.repo / "arquivo.txt"
        alvo.write_text("trabalho_do_dono", encoding="utf-8")
        indisponivel = {"tag": "x", "commit": None, "arvore_limpa": False, "disponivel": False}

        self.assertFalse(self.engine._rollback_to_checkpoint(indisponivel))
        self.assertEqual(alvo.read_text(encoding="utf-8"), "trabalho_do_dono")


if __name__ == "__main__":
    unittest.main()
