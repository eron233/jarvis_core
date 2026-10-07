"""
JARVIS - Stack Modular de Documentos

Camada opcional para parsing estrutural real de documentos usando Docling.
Mantem parsers nativos para formatos simples e nunca faz "string scraping"
de bytes binarios como se fosse extracao de documento.

Docling e carregado de forma lazy. PDFs exigem modelos pre-provisionados
quando downloads automaticos estiverem desabilitados.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class DocumentStackConfig:
    enabled: bool = False
    backend: str = "docling"
    device: str = "cpu"
    artifacts_path: Optional[Path] = None
    allow_model_download: bool = False
    pdf_ocr: bool = True
    pdf_tables: bool = True
    enable_remote_services: bool = False
    max_output_chars: int = 2_000_000
    chunk_chars: int = 4000
    chunk_overlap_chars: int = 400

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        project_root: Optional[Path] = None,
    ) -> "DocumentStackConfig":
        env = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT)

        artifacts_raw = (env.get("JARVIS_DOCLING_ARTIFACTS_PATH") or "").strip()
        artifacts_path: Optional[Path] = None
        if artifacts_raw:
            candidate = Path(artifacts_raw)
            artifacts_path = candidate if candidate.is_absolute() else root / candidate

        chunk_chars = max(500, int(env.get("JARVIS_DOCUMENT_CHUNK_CHARS", "4000")))
        chunk_overlap = max(0, int(env.get("JARVIS_DOCUMENT_CHUNK_OVERLAP_CHARS", "400")))
        chunk_overlap = min(chunk_overlap, chunk_chars // 2)

        return cls(
            enabled=_env_bool(env.get("JARVIS_DOCUMENT_PARSER_ENABLED"), False),
            backend=(env.get("JARVIS_DOCUMENT_PARSER_BACKEND") or "docling").strip(),
            device=(env.get("JARVIS_DOCUMENT_DEVICE") or "cpu").strip(),
            artifacts_path=artifacts_path,
            allow_model_download=_env_bool(
                env.get("JARVIS_DOCLING_ALLOW_MODEL_DOWNLOAD"),
                False,
            ),
            pdf_ocr=_env_bool(env.get("JARVIS_DOCLING_PDF_OCR"), True),
            pdf_tables=_env_bool(env.get("JARVIS_DOCLING_PDF_TABLES"), True),
            enable_remote_services=_env_bool(
                env.get("JARVIS_DOCLING_ENABLE_REMOTE_SERVICES"),
                False,
            ),
            max_output_chars=max(
                10_000,
                int(env.get("JARVIS_DOCUMENT_MAX_OUTPUT_CHARS", "2000000")),
            ),
            chunk_chars=chunk_chars,
            chunk_overlap_chars=chunk_overlap,
        )


class DocumentChunker:
    """Chunking deterministico, leve e independente de tokenizer."""

    def __init__(self, chunk_chars: int = 4000, overlap_chars: int = 400) -> None:
        self.chunk_chars = max(500, int(chunk_chars))
        self.overlap_chars = max(0, min(int(overlap_chars), self.chunk_chars // 2))

    def split(self, text: str) -> List[Dict[str, Any]]:
        normalized = str(text or "").replace("\r\n", "\n").strip()
        if not normalized:
            return []

        paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
        chunks: List[Dict[str, Any]] = []
        current = ""

        def flush() -> None:
            nonlocal current
            clean = current.strip()
            if not clean:
                current = ""
                return
            chunks.append(
                {
                    "index": len(chunks),
                    "text": clean,
                    "chars": len(clean),
                }
            )
            if self.overlap_chars > 0:
                current = clean[-self.overlap_chars :]
            else:
                current = ""

        for paragraph in paragraphs:
            if len(paragraph) > self.chunk_chars:
                if current.strip():
                    flush()
                start = 0
                while start < len(paragraph):
                    end = min(start + self.chunk_chars, len(paragraph))
                    piece = paragraph[start:end].strip()
                    if piece:
                        chunks.append(
                            {
                                "index": len(chunks),
                                "text": piece,
                                "chars": len(piece),
                            }
                        )
                    if end >= len(paragraph):
                        break
                    start = max(end - self.overlap_chars, start + 1)
                current = ""
                continue

            candidate = paragraph if not current.strip() else f"{current}\n\n{paragraph}"
            if len(candidate) <= self.chunk_chars:
                current = candidate
            else:
                flush()
                current = paragraph

        if current.strip():
            clean = current.strip()
            chunks.append(
                {
                    "index": len(chunks),
                    "text": clean,
                    "chars": len(clean),
                }
            )

        for index, chunk in enumerate(chunks):
            chunk["index"] = index
        return chunks


class DoclingBackend:
    """Parser estrutural real para PDF/Office/EPUB/HTML/etc."""

    PDF_EXTENSIONS = {"pdf"}
    SUPPORTED_EXTENSIONS = {
        "pdf",
        "docx",
        "xlsx",
        "pptx",
        "doc",
        "xls",
        "ppt",
        "rtf",
        "odt",
        "ods",
        "odp",
        "epub",
        "html",
        "htm",
        "xhtml",
        "md",
        "markdown",
        "asciidoc",
        "adoc",
        "tex",
        "latex",
        "csv",
        "png",
        "jpg",
        "jpeg",
        "tiff",
        "tif",
        "bmp",
        "webp",
        "eml",
        "msg",
    }

    def __init__(self, config: DocumentStackConfig) -> None:
        self.config = config
        self._generic_converter: Any = None
        self._pdf_converter: Any = None
        self._generic_error: Optional[str] = None
        self._pdf_error: Optional[str] = None

    @property
    def package_available(self) -> bool:
        return importlib.util.find_spec("docling") is not None

    @property
    def available(self) -> bool:
        return (
            self.config.enabled
            and self.config.backend == "docling"
            and self.package_available
        )

    @property
    def pdf_available(self) -> bool:
        if not self.available:
            return False
        if self.config.allow_model_download:
            return True
        return bool(
            self.config.artifacts_path
            and self.config.artifacts_path.exists()
            and self.config.artifacts_path.is_dir()
        )

    def supports(self, extension: str) -> bool:
        return extension.lower().lstrip(".") in self.SUPPORTED_EXTENSIONS

    def _load_generic(self) -> bool:
        if self._generic_converter is not None:
            return True
        if self._generic_error is not None:
            return False
        if not self.available:
            self._generic_error = (
                "Docling nao esta instalado ou JARVIS_DOCUMENT_PARSER_ENABLED=false."
            )
            return False
        try:
            from docling.document_converter import DocumentConverter

            self._generic_converter = DocumentConverter()
            return True
        except Exception as exc:
            self._generic_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def _load_pdf(self) -> bool:
        if self._pdf_converter is not None:
            return True
        if self._pdf_error is not None:
            return False
        if not self.pdf_available:
            self._pdf_error = (
                "PDF via Docling requer modelos locais em JARVIS_DOCLING_ARTIFACTS_PATH "
                "ou JARVIS_DOCLING_ALLOW_MODEL_DOWNLOAD=true."
            )
            return False
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import AcceleratorOptions, PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            kwargs: Dict[str, Any] = {
                "do_ocr": self.config.pdf_ocr,
                "do_table_structure": self.config.pdf_tables,
                "enable_remote_services": self.config.enable_remote_services,
                "accelerator_options": AcceleratorOptions(device=self.config.device),
            }
            if self.config.artifacts_path is not None:
                kwargs["artifacts_path"] = self.config.artifacts_path

            pipeline_options = PdfPipelineOptions(**kwargs)
            self._pdf_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                    )
                }
            )
            return True
        except Exception as exc:
            self._pdf_error = f"{exc.__class__.__name__}: {exc}"
            return False

    @staticmethod
    def _export_document(document: Any) -> Dict[str, Any]:
        markdown = None
        text = None
        structured = None

        try:
            markdown = document.export_to_markdown()
        except Exception:
            markdown = None

        try:
            text = document.export_to_text()
        except Exception:
            text = None

        try:
            structured = document.export_to_dict()
        except Exception:
            structured = None

        tables = []
        raw_tables = getattr(document, "tables", None)
        if raw_tables is not None:
            try:
                tables = list(raw_tables)
            except Exception:
                tables = []

        return {
            "markdown": str(markdown).strip() if markdown else None,
            "text": str(text).strip() if text else None,
            "structured": structured,
            "table_count": len(tables),
        }

    def parse(self, path: Path) -> Dict[str, Any]:
        extension = path.suffix.lower().lstrip(".")
        if not self.supports(extension):
            return {
                "status": "indisponivel",
                "motivo": f"Formato .{extension or 'desconhecido'} nao suportado pelo adapter Docling.",
            }

        is_pdf = extension in self.PDF_EXTENSIONS
        loaded = self._load_pdf() if is_pdf else self._load_generic()
        if not loaded:
            return {
                "status": "indisponivel",
                "motivo": self._pdf_error if is_pdf else self._generic_error,
            }

        converter = self._pdf_converter if is_pdf else self._generic_converter

        try:
            result = converter.convert(str(path))
            exported = self._export_document(result.document)
            primary = exported["markdown"] or exported["text"]
            if not primary:
                return {
                    "status": "erro",
                    "motivo": "Docling concluiu a conversao, mas nao produziu conteudo textual verificavel.",
                }

            primary = primary[: self.config.max_output_chars]
            return {
                "status": "sucesso",
                "metodo": "docling",
                "markdown": exported["markdown"][: self.config.max_output_chars]
                if exported["markdown"]
                else None,
                "texto": exported["text"][: self.config.max_output_chars]
                if exported["text"]
                else primary,
                "estruturado": exported["structured"],
                "quantidade_tabelas": exported["table_count"],
                "truncado": len(exported["markdown"] or exported["text"] or "") > self.config.max_output_chars,
            }
        except Exception as exc:
            return {
                "status": "erro",
                "motivo": f"Falha real no Docling: {exc.__class__.__name__}: {exc}",
            }


class DocumentStack:
    """Facade de parsing e chunking de documentos."""

    def __init__(self, config: Optional[DocumentStackConfig] = None) -> None:
        self.config = config or DocumentStackConfig.from_env()
        self.docling = DoclingBackend(self.config)
        self.chunker = DocumentChunker(
            chunk_chars=self.config.chunk_chars,
            overlap_chars=self.config.chunk_overlap_chars,
        )

    def parse(self, path: Path) -> Dict[str, Any]:
        result = self.docling.parse(path)
        if result.get("status") == "sucesso":
            source_text = result.get("markdown") or result.get("texto") or ""
            result["chunks"] = self.chunker.split(source_text)
            result["chunk_count"] = len(result["chunks"])
        else:
            result["chunks"] = []
            result["chunk_count"] = 0
        return result

    @staticmethod
    def file_sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "backend": self.config.backend,
            "docling_package_available": self.docling.package_available,
            "docling_available": self.docling.available,
            "pdf_available": self.docling.pdf_available,
            "device": self.config.device,
            "artifacts_path": str(self.config.artifacts_path)
            if self.config.artifacts_path
            else None,
            "allow_model_download": self.config.allow_model_download,
            "enable_remote_services": self.config.enable_remote_services,
            "chunk_chars": self.config.chunk_chars,
            "chunk_overlap_chars": self.config.chunk_overlap_chars,
            "fallback": "native_text_json_csv_or_explicit_unavailability",
        }
