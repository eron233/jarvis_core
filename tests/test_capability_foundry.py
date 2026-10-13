"""Capability Foundry: criterios verificaveis, limite de execucao e API."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid

from fastapi.testclient import TestClient
from interface.api.app import create_app
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.capability_foundry import CapabilityFoundry


class FoundryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.foundry = CapabilityFoundry(workspace=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_catalogo_nao_fabrica_instalacao_de_backend(self):
        cap = self.foundry.list_capabilities()
        self.assertEqual([a["id"] for a in cap], ["video.trim"])
        self.assertFalse(cap[0]["execucao_automatica"])
        self.assertEqual(cap[0]["backend"], "ffmpeg")

    def test_planejamento_tem_estados_honestos(self):
        with patch("runtime.capability_foundry.shutil.which", return_value=None):
            report = self.foundry.plan("Cortar um video em 30 segundos", "video.trim")
        self.assertEqual(report["status"], "dependencia_indisponivel")
        self.assertFalse(report["executada"])
        self.assertFalse(report["gerada"])
        unknown = self.foundry.plan("Crie um Spotify completo", "music.streaming")
        self.assertEqual(unknown["status"], "requer_pesquisa")
        self.assertFalse(unknown["gerada"])
        self.assertFalse(unknown["executada"])
        self.assertEqual(self.foundry.plan(" ")["status"], "entrada_invalida")

    @patch("runtime.capability_foundry.subprocess.run")
    def test_edicao_exige_aprovacao(self, run):
        report = self.foundry.trim_video("a.mp4", "b.mp4", 0, 2)
        self.assertEqual(report["status"], "aguardando_aprovacao")
        run.assert_not_called()

    @patch("runtime.capability_foundry.subprocess.run")
    def test_rejeita_traversal_arquivos_e_tempos_invalidos(self, run):
        (self.root / "in.mp4").write_bytes(b"validado_so_em_teste")
        vectors = [
            ("../in.mp4", "out.mp4", 0, 1),
            ("in.mp4", "../out.mp4", 0, 1),
            ("in.mp4", "-out.mp4", 0, 1),
            ("in.mp4", "in.mp4", 0, 1),
            ("in.mp4", "out.mp4", -1, 1),
            ("in.mp4", "out.mp4", 0, -1),
            ("in.mp4", "out.mp4", 0, math.nan),
            ("in.mp4", "out.mp4", True, 1),
            ("in.mp4", "out.mp4", 0, 3700),
        ]
        for source, dest, start, duration in vectors:
            with self.subTest(source=source, dest=dest, start=start, duration=duration):
                result = self.foundry.trim_video(source, dest, start, duration, approved=True)
                self.assertEqual(result["status"], "entrada_invalida")
        run.assert_not_called()

    @patch("runtime.capability_foundry.subprocess.run")
    def test_link_de_entrada_bloqueado_e_saida_nao_sobrescrita(self, run):
        external = self.root.parent / ("external_sample_" + self.root.name + ".mp4")
        external.write_bytes(b"outside")
        try:
            (self.root / "in.mp4").symlink_to(external)
            out = self.foundry.trim_video("in.mp4", "out.mp4", 0, 1, approved=True)
            self.assertEqual(out["status"], "entrada_indisponivel")
        finally:
            external.unlink(missing_ok=True)
        (self.root / "in.mp4").unlink()
        (self.root / "in.mp4").write_bytes(b"valid")
        (self.root / "out.mp4").write_bytes(b"existing")
        result = self.foundry.trim_video("in.mp4", "out.mp4", 0, 1, approved=True)
        self.assertEqual(result["status"], "saida_existente")
        self.assertEqual((self.root / "out.mp4").read_bytes(), b"existing")
        run.assert_not_called()

    @patch("runtime.capability_foundry.subprocess.run")
    def test_dep_ausente_nao_gera_sucesso(self, run):
        (self.root / "in.mp4").write_bytes(b"fake")
        with patch("runtime.capability_foundry.shutil.which", return_value=None):
            out = self.foundry.trim_video("in.mp4", "out.mp4", 0, 1, approved=True)
        self.assertEqual(out["status"], "dependencia_indisponivel")
        self.assertFalse(out["executado"])
        run.assert_not_called()

    @patch("runtime.capability_foundry.subprocess.run")
    def test_saida_criada_apos_transcodificacao_reporta_nao_homologado(self, run):
        (self.root / "in.mp4").write_bytes(b"fake")
        def fake_ffmpeg(args, **kwargs):
            Path(args[-1]).write_bytes(b"mp4_outputs_placeholder")
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        run.side_effect = fake_ffmpeg
        with patch("runtime.capability_foundry.shutil.which", return_value="/usr/bin/ffmpeg"):
            out = self.foundry.trim_video("in.mp4", "out.mp4", 0, 1, approved=True)
        self.assertEqual(out["status"], "arquivo_criado_nao_homologado")
        self.assertFalse(out["resultado_verificado_por_reproducao"])
        self.assertTrue((self.root / "out.mp4").exists())
        argv = run.call_args.args[0]
        self.assertIn("-nostdin", argv)
        self.assertIn("-f", argv)
        self.assertNotIn("sh", argv)
        self.assertFalse(list(self.root.glob(".jarvis-video-*")))

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg nao instalado neste runner")
    def test_video_real_com_ffmpeg(self):
        src = self.root / "in.mp4"
        creation = subprocess.run(
            [shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=blue:s=96x64:r=10:d=2",
             "-c:v", "mpeg4", "-y", str(src)],
            capture_output=True, timeout=30,
        )
        if creation.returncode != 0:
            self.skipTest("FFmpeg nao suporta gerador de video de teste")
        out = self.foundry.trim_video("in.mp4", "out.mp4", .4, .6, approved=True)
        self.assertEqual(out["status"], "arquivo_criado_nao_homologado", out)
        self.assertGreater(out["tamanho_bytes"], 0)
        if shutil.which("ffprobe"):
            probe = subprocess.run(
                [shutil.which("ffprobe"), "-v", "error",
                 "-select_streams", "v:0", "-show_entries", "stream=codec_name",
                 "-of", "default=nw=1", str(self.root / "out.mp4")],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(probe.returncode, 0)
            self.assertIn("codec_name", probe.stdout)


class FoundryAPITests(unittest.TestCase):
    def setUp(self):
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()
        self.client = TestClient(create_app(
            runtime=self.runtime, api_token="foundry-test-token",
            trusted_device_id="foundry-test-device",
        ))

    def _headers(self):
        return {
            "X-Jarvis-Token": "foundry-test-token",
            "X-Jarvis-Device-Id": "foundry-test-device",
            "X-Jarvis-Nonce": str(uuid.uuid4()),
            "X-Jarvis-Timestamp": str(int(time.time())),
        }

    def test_endpoints_sao_protegidos(self):
        self.assertNotEqual(self.client.get("/api/foundry/capacidades").status_code, 200)
        self.assertNotEqual(self.client.post("/api/foundry/planejar", json={"pedido":"video"}).status_code, 200)
        self.assertNotEqual(self.client.post("/api/foundry/video/cortar", json={
            "arquivo_origem":"in.mp4", "arquivo_saida":"out.mp4",
            "inicio_segundos":0, "duracao_segundos":1, "aprovado":True
        }).status_code, 200)

    def test_catalogo_e_planejamento_api(self):
        r = self.client.get("/api/foundry/capacidades", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["capacidades"][0]["id"], "video.trim")
        p = self.client.post("/api/foundry/planejar", headers=self._headers(),
                             json={"pedido": "Quero um editor de video", "capacidade":"video.trim"})
        self.assertEqual(p.status_code, 200)
        self.assertFalse(p.json()["executada"])

    def test_sem_aprovacao_video_nao_aciona_ffmpeg(self):
        with patch.object(self.runtime.capability_foundry, "trim_video",
                          return_value={"status":"aguardando_aprovacao"}) as fn:
            r = self.client.post("/api/foundry/video/cortar", headers=self._headers(), json={
                "arquivo_origem":"in.mp4", "arquivo_saida":"out.mp4",
                "inicio_segundos":0, "duracao_segundos":1,
                "aprovado":False,
            })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(fn.call_args.kwargs["approved"])


if __name__ == "__main__":
    unittest.main()
