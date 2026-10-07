"""Testes do ponto 3: visão/OCR modular do JARVIS."""

from pathlib import Path
import tempfile
import unittest

from learning.image_vision_engine import ImageVisionEngine
from learning.vision_stack import PaddleOCRv6Backend, VisionStackConfig


class _FakePaddleResult:
    @property
    def json(self):
        return {
            "res": {
                "rec_texts": ["Olá", "mundo", "baixo"],
                "rec_scores": [0.99, 0.88, 0.10],
                "rec_boxes": [
                    [1, 2, 30, 12],
                    [2, 20, 40, 32],
                    [3, 40, 25, 52],
                ],
            }
        }


class _FakePaddlePipeline:
    def predict(self, path):
        return [_FakePaddleResult()]


class _FakeVisionStack:
    def extract_text(self, path):
        return {
            "status": "sucesso",
            "texto": "Texto real do OCR",
            "linhas": [{"texto": "Texto real do OCR", "confianca": 0.97, "caixa": [0, 0, 10, 10]}],
            "quantidade_linhas": 1,
            "confianca_media": 0.97,
            "metodo": "fake-ocr",
        }

    def describe_image(self, path):
        return {
            "status": "sucesso",
            "descricao": "Uma janela do sistema com texto.",
            "metodo": "fake-vlm",
        }

    def ask_image(self, path, question):
        return {
            "status": "sucesso",
            "resposta": f"Resposta visual para: {question}",
            "metodo": "fake-vlm",
        }

    def parse_document_visual(self, path):
        return {
            "status": "sucesso",
            "markdown": "# Documento\nConteúdo",
            "estruturado": [{"type": "text"}],
            "paginas": 1,
            "metodo": "fake-document-vl",
        }

    def status(self):
        return {
            "enabled": True,
            "ocr": {"available": True},
            "document_vl": {"available": True},
            "general_vision": {"available": True},
        }


class _UnavailableVisionStack:
    def extract_text(self, path):
        return {
            "status": "indisponivel",
            "texto": None,
            "linhas": [],
            "motivo": "OCR não configurado.",
        }

    def describe_image(self, path):
        return {
            "status": "indisponivel",
            "descricao": None,
            "motivo": "VLM não configurado.",
        }

    def ask_image(self, path, question):
        return {
            "status": "indisponivel",
            "resposta": None,
            "motivo": "VLM não configurado.",
        }

    def parse_document_visual(self, path):
        return {
            "status": "indisponivel",
            "markdown": None,
            "estruturado": [],
            "motivo": "Parser não configurado.",
        }

    def status(self):
        return {"enabled": False}


class VisionStackConfigTests(unittest.TestCase):
    def test_defaults_are_safe_for_weak_hardware(self):
        config = VisionStackConfig.from_env(environ={}, project_root=Path("."))
        self.assertFalse(config.enabled)
        self.assertEqual(config.ocr_device, "cpu")
        self.assertEqual(config.ocr_detection_model, "PP-OCRv6_small_det")
        self.assertEqual(config.ocr_recognition_model, "PP-OCRv6_small_rec")
        self.assertFalse(config.ocr_allow_model_download)
        self.assertFalse(config.document_vl_enabled)
        self.assertFalse(config.general_vision_enabled)

    def test_environment_can_select_tiny_models(self):
        config = VisionStackConfig.from_env(
            environ={
                "JARVIS_VISION_ADVANCED_ENABLED": "true",
                "JARVIS_OCR_DETECTION_MODEL": "PP-OCRv6_tiny_det",
                "JARVIS_OCR_RECOGNITION_MODEL": "PP-OCRv6_tiny_rec",
                "JARVIS_OCR_MIN_SCORE": "0.60",
                "JARVIS_GENERAL_VISION_ENABLED": "true",
                "JARVIS_GENERAL_VISION_ENDPOINT": "http://localhost:2020/v1",
            },
            project_root=Path("."),
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.ocr_detection_model, "PP-OCRv6_tiny_det")
        self.assertEqual(config.ocr_recognition_model, "PP-OCRv6_tiny_rec")
        self.assertEqual(config.ocr_min_score, 0.60)
        self.assertTrue(config.general_vision_enabled)


class PaddleOCRParsingTests(unittest.TestCase):
    def test_backend_filters_by_real_score_and_preserves_boxes(self):
        config = VisionStackConfig(
            enabled=True,
            ocr_min_score=0.35,
            ocr_allow_model_download=True,
        )
        backend = PaddleOCRv6Backend(config)
        backend._pipeline = _FakePaddlePipeline()

        result = backend.extract_text(Path("fake.png"))

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["texto"], "Olá\nmundo")
        self.assertEqual(result["quantidade_linhas"], 2)
        self.assertAlmostEqual(result["confianca_media"], 0.935)
        self.assertEqual(result["linhas"][0]["caixa"], [1, 2, 30, 12])


class ImageVisionEngineTests(unittest.TestCase):
    def test_builds_context_only_from_real_provider_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "print.png"
            path.write_bytes(b"not-a-real-png-but-provider-is-faked")

            engine = ImageVisionEngine(vision_stack=_FakeVisionStack())
            result = engine.analyze_image_and_build_context(
                path,
                user_hint="Tela de configuração",
            )

            self.assertEqual(result["status"], "sucesso")
            self.assertEqual(result["texto_extraido_ocr"], "Texto real do OCR")
            self.assertEqual(
                result["visao_geral"]["descricao"],
                "Uma janela do sistema com texto.",
            )
            self.assertIn("OCR real detectou", result["pre_contexto_visual"])
            self.assertIn("Dica do usuário", result["pre_contexto_visual"])

    def test_binary_strings_are_not_treated_as_ocr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fake.png"
            path.write_bytes(
                b"PNG....PASSWORD=nao-e-ocr....TEXTO_BINARIO_QUE_ANTES_SERIA_LIDO"
            )

            engine = ImageVisionEngine(vision_stack=_UnavailableVisionStack())
            result = engine.analyze_image_and_build_context(path)

            self.assertEqual(result["status"], "sucesso")
            self.assertIsNone(result["texto_extraido_ocr"])
            self.assertEqual(result["ocr"]["status"], "indisponivel")
            self.assertNotIn("PASSWORD=nao-e-ocr", result["pre_contexto_visual"])
            self.assertNotIn("TEXTO_BINARIO", result["pre_contexto_visual"])

    def test_visual_question_uses_provider_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "image.jpg"
            path.write_bytes(b"x")
            engine = ImageVisionEngine(vision_stack=_FakeVisionStack())

            result = engine.ask_image(path, "O que há na tela?")

            self.assertEqual(result["status"], "sucesso")
            self.assertIn("O que há na tela?", result["resposta"])

    def test_complex_document_is_explicitly_on_demand(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "doc.png"
            path.write_bytes(b"x")
            engine = ImageVisionEngine(vision_stack=_FakeVisionStack())

            result = engine.parse_complex_document(path)

            self.assertEqual(result["status"], "sucesso")
            self.assertIn("# Documento", result["markdown"])


if __name__ == "__main__":
    unittest.main()
