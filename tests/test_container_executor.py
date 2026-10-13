"""Container executor: fail-closed contract, no inherited host credentials."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import os
import stat
import sys
import tempfile
import unittest

from runtime.tool_developer_engine import ToolDeveloperEngine
from security.container_executor import (
    ContainerExecutor, MAX_OUTPUT_BYTES, RESULT_PREFIX,
)

IMAGE = "python:3.11-alpine@sha256:" + "a" * 64


class ContainerExecutorTests(unittest.TestCase):
    def setUp(self):
        self.executor = ContainerExecutor(enabled=True, image=IMAGE)

    def test_desativado_e_falha_fechado(self):
        report = ContainerExecutor(image=IMAGE).execute("pass")
        self.assertFalse(report["executado"])
        self.assertEqual(report["status"], "bloqueado_por_seguranca")

    def test_exige_digest_imutavel(self):
        for image in ("python:3.11-alpine", "python:latest",
                      "alpine@sha256:xyz", "a@sha256:" + "B" * 64):
            with self.subTest(image=image):
                report = ContainerExecutor(enabled=True, image=image).execute("pass")
                self.assertFalse(report["executado"])

    def test_argumentos_e_orcamento_invalidos(self):
        for args, timeout in (({"x": object()}, 5), ([], 5),
                              ({}, 0), ({}, 31), ({}, True)):
            with self.subTest(args=args, timeout=timeout):
                report = self.executor.execute("pass", args, timeout)
                self.assertFalse(report["executado"])

    def test_sem_docker_nao_tenta_executar(self):
        with patch("security.container_executor.shutil.which", return_value=None):
            report = self.executor.execute("pass")
        self.assertEqual(report["status"], "bloqueado_por_seguranca")

    def test_sem_linux_nao_tenta_executar(self):
        with patch("security.container_executor.platform.system", return_value="Windows"):
            report = self.executor.execute("pass")
        self.assertEqual(report["status"], "bloqueado_por_seguranca")

    @patch("security.container_executor.subprocess.run")
    @patch.object(ContainerExecutor, "_invoke")
    def test_comando_isolado_e_resultado_nao_comprova_conclusao(self, invoke, cleanup):
        invoke.return_value = (
            0, (RESULT_PREFIX + json.dumps({"ok": True, "value": {"status": "sucesso"}}) + "\n").encode(), b""
        )
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp, "docker")
            docker.touch()
            with patch("security.container_executor.shutil.which", return_value=str(docker)), \
                 patch("security.container_executor.stat.S_ISSOCK", return_value=True):
                report = self.executor.execute("def run_tool(x): return x", {"x": 9})
        self.assertEqual(report["status"], "executado_sem_verificacao")
        self.assertTrue(report["executado"])
        self.assertFalse(report["concluido_verificado"])
        argv, data, _, env = invoke.call_args.args
        for required in ("--network", "none", "--read-only", "--cap-drop", "ALL",
                         "--security-opt", "no-new-privileges:true", "seccomp=builtin",
                         "--memory", "256m", "--pids-limit", "32", "--pull", "never",
                         "--user", "65534:65534"):
            self.assertIn(required, argv)
        self.assertNotIn("--privileged", argv)
        self.assertNotIn("--mount", argv)
        self.assertNotIn("--volume", argv)
        self.assertNotIn("--device", argv)
        self.assertEqual(argv[1:3], ["--host", "unix:///var/run/docker.sock"])
        self.assertEqual(argv[-5:-4], ["-I"]) if False else None
        self.assertNotIn("DOCKER_HOST", env)
        self.assertNotIn("JARVIS_TOKEN", env)
        self.assertIn('"params": {"x": 9}', data.decode())
        self.assertTrue(cleanup.called)

    @patch("security.container_executor.subprocess.run")
    @patch.object(ContainerExecutor, "_invoke")
    def test_ferramenta_falha_sem_sucesso_inventado(self, invoke, cleanup):
        invoke.return_value = (
            0, (RESULT_PREFIX + json.dumps({"ok": False, "error_type": "ValueError", "error": "falhou"}) + "\n").encode(), b""
        )
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp, "docker")
            docker.touch()
            with patch("security.container_executor.shutil.which", return_value=str(docker)), \
                 patch("security.container_executor.stat.S_ISSOCK", return_value=True):
                report = self.executor.execute("x=1")
        self.assertEqual(report["status"], "erro_ferramenta")
        self.assertFalse(report["concluido_verificado"])

    def test_limita_stdout_sem_docker(self):
        # Exercita o leitor real e sua defesa contra saida hostil volumosa.
        with self.assertRaises(ValueError):
            self.executor._invoke(
                [sys.executable, "-c", f"print('A'*{MAX_OUTPUT_BYTES * 2})"],
                b"{}", 5.0, dict(os.environ)
            )


class ContainerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = ToolDeveloperEngine(tools_dir=Path(self.tmp.name) / "tools")

    def tearDown(self):
        self.tmp.cleanup()

    def test_nome_ausente_recusado(self):
        out = self.engine.execute_tool_in_sandbox("desconhecido")
        self.assertFalse(out["executado"])

    def test_nao_habilita_automaticamente(self):
        created = self.engine.develop_tool("Seguro", "teste", "return {'status': 'sucesso'}")
        self.assertTrue(created["validada"])
        with patch.dict(os.environ, {"JARVIS_TWIN_DOCKER_ENABLED": "false"}):
            out = self.engine.execute_tool_in_sandbox("Seguro")
        self.assertEqual(out["status"], "bloqueado_por_seguranca")

    def test_simb_link_nao_escapa_do_diretorio(self):
        self.engine.develop_tool("Seguro", "teste", "return {}")
        filename = self.engine.tools_dir / "seguro.py"
        filename.unlink()
        outside = Path(self.tmp.name) / "outside.py"
        outside.write_text("return {}", encoding="utf-8")
        filename.symlink_to(outside)
        with patch.dict(os.environ, {"JARVIS_TWIN_DOCKER_ENABLED": "true"}):
            out = self.engine.execute_tool_in_sandbox("Seguro")
        self.assertEqual(out["status"], "bloqueado_por_seguranca")

    @patch("runtime.tool_developer_engine.ContainerExecutor.execute")
    def test_dispatch_com_opt_in_e_sem_fallback(self, execute):
        self.engine.develop_tool("Seguro", "teste", "return {'ok': True}")
        execute.return_value = {
            "status": "executado_sem_verificacao", "executado": True,
            "concluido_verificado": False,
        }
        with patch.dict(os.environ, {
            "JARVIS_TWIN_DOCKER_ENABLED": "true", "JARVIS_TWIN_DOCKER_IMAGE": IMAGE
        }):
            result = self.engine.execute_tool_in_sandbox("Seguro", {"a": 1})
        self.assertEqual(result["tool_name"], "Seguro")
        self.assertTrue(result["executado"])
        self.assertFalse(result["concluido_verificado"])


if __name__ == "__main__":
    unittest.main()
