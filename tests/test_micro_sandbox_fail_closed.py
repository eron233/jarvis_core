"""Regressoes do microprocesso: entradas, logs e resultados honestos."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os
import tempfile
import unittest

from security.lightweight_sandbox_engine import UltraLightweightSandboxEngine


class MicroSandboxFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.engine = UltraLightweightSandboxEngine(data_dir=self.base / "reports")

    def tearDown(self):
        self.tmp.cleanup()

    def test_nomes_maliciosos_nao_criam_arquivos(self):
        for name in ("../outside", "../../outside", "sub/path", "a\\b", "..", ""):
            with self.subTest(name=name):
                resp = self.engine.execute_in_microsandbox("a = 1", tool_name=name)
                self.assertEqual(resp["status"], "nome_invalido")
                self.assertFalse(resp["sucesso"])
        self.assertFalse((self.base / "outside.py").exists())
        self.assertEqual(list((self.base / "reports").glob("*")), [])

    @patch("security.lightweight_sandbox_engine.subprocess.run")
    def test_saida_invalida_nao_vira_sucesso(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="isto nao e json", stderr="")
        resp = self.engine.execute_in_microsandbox("a = 1", "teste")
        self.assertEqual(resp["status"], "erro_saida_invalida")
        self.assertFalse(resp["sucesso"])

    @patch("security.lightweight_sandbox_engine.subprocess.run")
    def test_limites_ausentes_nao_viram_sucesso(self, run):
        run.return_value = SimpleNamespace(
            returncode=0, stdout='{"status":"sucesso","limites_aplicados":[]}', stderr=""
        )
        resp = self.engine.execute_in_microsandbox("a = 1", "teste")
        self.assertEqual(resp["status"], "limites_indisponiveis")
        self.assertFalse(resp["sucesso"])

    @patch("security.lightweight_sandbox_engine.subprocess.run")
    def test_filtrado_ambiente_e_python_isolado(self, run):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout='{"status":"sucesso","limites_aplicados":["RLIMIT_CPU","RLIMIT_AS"]}',
            stderr="",
        )
        with patch.dict(os.environ, {"JARVIS_SENTINEL_SECRET": "nao_vazar"}):
            resp = self.engine.execute_in_microsandbox("a = 1", "teste")
        self.assertTrue(resp["sucesso"])
        args, kwargs = run.call_args
        self.assertEqual(args[0][1], "-I")
        self.assertNotIn("JARVIS_SENTINEL_SECRET", kwargs["env"])
        self.assertNotIn("PATH", kwargs["env"])


if __name__ == "__main__":
    unittest.main()
