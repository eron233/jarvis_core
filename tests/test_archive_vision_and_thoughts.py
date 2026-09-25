"""
Testes unitários cobrindo compactação/descompactação, pré-contexto visual de imagem e stream de pensamentos privados do Dono.
"""

from pathlib import Path
import tempfile
import unittest

from learning.image_vision_engine import ImageVisionEngine
from runtime.file_archive_engine import FileArchiveEngine
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.thought_stream_engine import ThoughtStreamEngine


class ArchiveVisionAndThoughtsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_file_archive_engine(self) -> None:
        archive_engine = FileArchiveEngine(archive_dir=self.tmp_path)

        # Cria arquivo de teste
        sample_file = self.tmp_path / "sample.txt"
        sample_file.write_text("Arquivo para teste de zip.", encoding="utf-8")

        # Compacta
        comp_res = archive_engine.compress_files(source_paths=[sample_file], archive_name="test_zip", format_type="zip")
        self.assertEqual(comp_res["status"], "sucesso")
        zip_path = Path(comp_res["arquivo_compactado"])
        self.assertTrue(zip_path.exists())

        # Descompacta
        decomp_res = archive_engine.decompress_archive(archive_path=zip_path, destination_dir=self.tmp_path / "out")
        self.assertEqual(decomp_res["status"], "sucesso")

    def test_image_vision_engine(self) -> None:
        vision_engine = ImageVisionEngine()

        img_file = self.tmp_path / "screenshot.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        res = vision_engine.analyze_image_and_build_context(image_path=img_file, user_hint="Print de teste")
        self.assertEqual(res["status"], "sucesso")
        self.assertIn("pre_contexto_visual", res)
        # A imagem de teste é um PNG 1x1 -> dimensões devem ser lidas de verdade do cabeçalho IHDR
        self.assertEqual(res["largura_px"], 1)
        self.assertEqual(res["altura_px"], 1)
        self.assertIn("ocr_disponivel", res)
        self.assertFalse(res["ocr_disponivel"])  # sem pytesseract instalado no ambiente de teste
        self.assertEqual(res["texto_extraido_ocr"], "")

    def test_image_vision_engine_png_5x3_dimensions(self) -> None:
        """PNG maior (5x3) gerado manualmente, para confirmar o parsing correto do cabeçalho IHDR."""
        import struct
        import zlib

        vision_engine = ImageVisionEngine()

        width, height = 5, 3
        png_signature = b"\x89PNG\r\n\x1a\n"

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # RGB, 8 bits
        raw_scanlines = b""
        for _ in range(height):
            raw_scanlines += b"\x00" + b"\x00\x00\x00" * width  # filtro None + pixels pretos
        idat_data = zlib.compress(raw_scanlines)

        png_bytes = (
            png_signature
            + chunk(b"IHDR", ihdr_data)
            + chunk(b"IDAT", idat_data)
            + chunk(b"IEND", b"")
        )

        img_file = self.tmp_path / "generated.png"
        img_file.write_bytes(png_bytes)

        res = vision_engine.analyze_image_and_build_context(image_path=img_file)
        self.assertEqual(res["status"], "sucesso")
        self.assertEqual(res["largura_px"], width)
        self.assertEqual(res["altura_px"], height)

    def test_thought_stream_engine(self) -> None:
        thought_engine = ThoughtStreamEngine(thoughts_dir=self.tmp_path)

        thought_engine.record_thought(
            context_action="Analisar pedido do dono",
            internal_reasoning="Verificando se há solicitações de auditoria ou testes solicitados pelo dono.",
            owner_opinion_eval="O dono solicitou um teste de invasão no seu próprio projeto autorizado.",
            potential_risks_identified=["Alerta de segurança"],
        )

        # Acesso negado para não-dono
        denied = thought_engine.get_owner_thoughts_stream(is_authenticated_owner=False)
        self.assertEqual(denied["status"], "negado")

        # Acesso permitido para o dono
        allowed = thought_engine.get_owner_thoughts_stream(is_authenticated_owner=True)
        self.assertEqual(allowed["status"], "sucesso")
        self.assertEqual(len(allowed["ultimos_pensamentos"]), 1)

    def test_runtime_integration_of_new_engines(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "file_archive_engine"))
        self.assertTrue(hasattr(runtime, "image_vision_engine"))
        self.assertTrue(hasattr(runtime, "thought_stream_engine"))


if __name__ == "__main__":
    unittest.main()
