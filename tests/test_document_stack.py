"""Testes do ponto 4: documentos estruturados e preservacao integral."""

from pathlib import Path
import tempfile
import unittest

from learning.document_stack import DocumentChunker, DocumentStackConfig
from learning.research_knowledge_engine import ResearchKnowledgeEngine
from learning.universal_file_extractor import UniversalFileExtractor


class _FakeDocumentStack:
    def __init__(self):
        self.chunker = DocumentChunker(chunk_chars=80, overlap_chars=10)

    def parse(self, path: Path):
        return {
            "status": "sucesso",
            "metodo": "fake-docling",
            "markdown": "# Relatório\n\nTabela importante\n\nValor final: 42",
            "texto": "Relatório\nTabela importante\nValor final: 42",
            "estruturado": {"type": "document"},
            "quantidade_tabelas": 1,
            "truncado": False,
            "chunks": self.chunker.split(
                "# Relatório\n\nTabela importante\n\nValor final: 42"
            ),
            "chunk_count": 1,
        }

    def status(self):
        return {
            "enabled": True,
            "backend": "fake-docling",
            "docling_available": True,
        }


class _UnavailableDocumentStack:
    def __init__(self):
        self.chunker = DocumentChunker(chunk_chars=80, overlap_chars=10)

    def parse(self, path: Path):
        return {
            "status": "indisponivel",
            "metodo": "docling",
            "motivo": "Docling não configurado.",
            "chunks": [],
            "chunk_count": 0,
        }

    def status(self):
        return {"enabled": False, "docling_available": False}


class DocumentStackConfigTests(unittest.TestCase):
    def test_defaults_are_local_first_and_download_safe(self):
        config = DocumentStackConfig.from_env(environ={}, project_root=Path("."))
        self.assertFalse(config.enabled)
        self.assertEqual(config.backend, "docling")
        self.assertEqual(config.device, "cpu")
        self.assertFalse(config.allow_model_download)
        self.assertFalse(config.enable_remote_services)
        self.assertTrue(config.pdf_ocr)
        self.assertTrue(config.pdf_tables)

    def test_chunker_preserves_long_content_in_multiple_chunks(self):
        chunker = DocumentChunker(chunk_chars=500, overlap_chars=50)
        text = "\n\n".join(
            [
                "A" * 300,
                "B" * 300,
                "C" * 300,
            ]
        )
        chunks = chunker.split(text)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk["chars"] <= 500 for chunk in chunks))
        self.assertEqual([chunk["index"] for chunk in chunks], list(range(len(chunks))))


class UniversalDocumentIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        self.knowledge = ResearchKnowledgeEngine(
            knowledge_dir=self.root / "knowledge",
            db_path=self.root / "knowledge" / "knowledge.db",
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_structured_document_is_preserved_as_chunks_and_artifacts(self):
        pdf = self.root / "relatorio.pdf"
        pdf.write_bytes(b"%PDF-1.7 fake fixture content")

        extractor = UniversalFileExtractor(
            knowledge_engine=self.knowledge,
            document_stack=_FakeDocumentStack(),
            artifact_dir=self.root / "artifacts",
        )
        result = extractor.extract_and_ingest_file(pdf)

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["parser"], "fake-docling")
        self.assertEqual(result["quantidade_tabelas"], 1)
        self.assertGreaterEqual(result["chunk_count"], 1)
        self.assertTrue(Path(result["artefatos"]["markdown"]).exists())
        self.assertTrue(Path(result["artefatos"]["manifest"]).exists())

        item_id = result["item_conhecimento"]["item_id"]
        chunks = self.knowledge.get_document_chunks(item_id)
        self.assertEqual(len(chunks), result["chunk_count"])
        self.assertIn("Valor final: 42", "\n".join(chunk["conteudo"] for chunk in chunks))
        self.assertTrue(all(chunk["source_sha256"] == result["sha256"] for chunk in chunks))

    def test_binary_strings_are_not_used_as_document_extraction(self):
        pdf = self.root / "segredo.pdf"
        pdf.write_bytes(
            b"%PDF BINARY SECRET_PASSWORD=isto-nao-e-texto-do-documento END"
        )

        extractor = UniversalFileExtractor(
            knowledge_engine=self.knowledge,
            document_stack=_UnavailableDocumentStack(),
            artifact_dir=self.root / "artifacts",
        )
        result = extractor.extract_and_ingest_file(pdf)

        self.assertEqual(result["status"], "indisponivel")
        self.assertIn("Docling", result["motivo"])
        self.assertEqual(self.knowledge.list_all_knowledge(), [])

    def test_unknown_binary_format_is_rejected_explicitly(self):
        binary = self.root / "payload.bin"
        binary.write_bytes(b"VISIBLE_STRING_THAT_MUST_NOT_BE_INGESTED")

        extractor = UniversalFileExtractor(
            knowledge_engine=self.knowledge,
            document_stack=_UnavailableDocumentStack(),
            artifact_dir=self.root / "artifacts",
        )
        result = extractor.extract_and_ingest_file(binary)

        self.assertEqual(result["status"], "indisponivel")
        self.assertIn("não possui parser confiável", result["motivo"])
        self.assertEqual(self.knowledge.search_document_chunks("VISIBLE_STRING"), [])

    def test_native_text_is_chunked_and_searchable_in_full(self):
        text_file = self.root / "notas.txt"
        text_file.write_text(
            "Primeiro parágrafo.\n\n"
            + ("conteudo intermediario " * 30)
            + "\n\nFrase rara no final: ORQUIDEA-NEON.",
            encoding="utf-8",
        )

        extractor = UniversalFileExtractor(
            knowledge_engine=self.knowledge,
            document_stack=_UnavailableDocumentStack(),
            artifact_dir=self.root / "artifacts",
        )
        result = extractor.extract_and_ingest_file(text_file)

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["parser"], "native_utf8_text")
        matches = self.knowledge.search_document_chunks("ORQUIDEA-NEON")
        self.assertEqual(len(matches), 1)
        self.assertIn("ORQUIDEA-NEON", matches[0]["conteudo"])


if __name__ == "__main__":
    unittest.main()
