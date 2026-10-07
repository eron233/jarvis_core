"""
JARVIS - Ingestao Estruturada de Arquivos

Responsavel por:
- extrair formatos simples com parsers nativos leves
- delegar documentos estruturados/binarios ao Docling
- preservar o conteudo integral em chunks e artefatos locais
- registrar resumo/catalogo no ResearchKnowledgeEngine
- nunca extrair "strings imprimiveis" de binarios como se fossem documento
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from learning.document_stack import DocumentStack, DocumentStackConfig
from learning.research_knowledge_engine import ResearchKnowledgeEngine


_SIMPLE_TEXT_EXTENSIONS = {
    "txt",
    "md",
    "markdown",
    "py",
    "c",
    "h",
    "cpp",
    "hpp",
    "java",
    "js",
    "ts",
    "tsx",
    "jsx",
    "css",
    "scss",
    "sh",
    "bat",
    "cmd",
    "ps1",
    "toml",
    "yaml",
    "yml",
    "ini",
    "cfg",
    "sql",
    "rs",
    "go",
    "rb",
    "php",
    "swift",
    "kt",
    "kts",
}

_DOCLING_EXTENSIONS = {
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
    "asciidoc",
    "adoc",
    "tex",
    "latex",
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


class UniversalFileExtractor:
    """Ingestor de arquivos com contratos reais por tipo de formato."""

    def __init__(
        self,
        knowledge_engine: Optional[ResearchKnowledgeEngine] = None,
        document_stack: Optional[DocumentStack] = None,
        artifact_dir: Optional[Path] = None,
    ) -> None:
        self.knowledge_engine = knowledge_engine or ResearchKnowledgeEngine()
        self.document_stack = document_stack or DocumentStack()
        self.artifact_dir = Path(
            artifact_dir
            or (self.knowledge_engine.knowledge_dir / "documents")
        )
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def extract_and_ingest_file(
        self,
        file_path: str | Path,
        custom_title: Optional[str] = None,
        topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Extrai, preserva e ingere um arquivo usando o parser apropriado."""

        path = Path(file_path)
        if not path.exists():
            return {"status": "erro", "motivo": f"Arquivo {file_path} não encontrado no sistema."}
        if not path.is_file():
            return {"status": "erro", "motivo": f"O caminho {file_path} não é um arquivo regular."}

        title = custom_title or path.stem
        extension = path.suffix.lower().lstrip(".")
        extraction = self._extract(path, extension)

        if extraction.get("status") != "sucesso":
            return {
                "status": extraction.get("status", "erro"),
                "arquivo": path.name,
                "formato_detectado": extension or "desconhecido",
                "motivo": extraction.get("motivo", "Extracao indisponivel."),
                "parser": extraction.get("metodo"),
            }

        raw_text = str(
            extraction.get("markdown")
            or extraction.get("texto")
            or ""
        ).strip()
        if not raw_text:
            return {
                "status": "erro",
                "arquivo": path.name,
                "formato_detectado": extension or "desconhecido",
                "motivo": f"O parser executou, mas nenhum texto verificavel foi extraído de {path.name}.",
                "parser": extraction.get("metodo"),
            }

        source_hash = self._sha256(path)
        chunks = extraction.get("chunks")
        if not isinstance(chunks, list):
            chunks = self.document_stack.chunker.split(raw_text)

        artifacts = self._persist_extraction_artifacts(
            path=path,
            title=title,
            extension=extension,
            source_hash=source_hash,
            raw_text=raw_text,
            extraction=extraction,
            chunks=chunks,
        )

        source_type = f"arquivo_{extension}" if extension else "arquivo_generico"
        knowledge_item = self.knowledge_engine.ingest_source(
            title=title,
            source_type=source_type,
            raw_text=raw_text,
            topics=topics or [extension or "desconhecido", "ingestao_documental"],
        )

        chunk_manifest = self.knowledge_engine.ingest_document_chunks(
            item_id=knowledge_item["item_id"],
            chunks=chunks,
            source_path=str(path),
            source_sha256=source_hash,
        )

        return {
            "status": "sucesso",
            "arquivo": path.name,
            "formato_detectado": extension or "desconhecido",
            "tamanho_arquivo_bytes": path.stat().st_size,
            "sha256": source_hash,
            "parser": extraction.get("metodo"),
            "texto_chars": len(raw_text),
            "chunk_count": len(chunks),
            "quantidade_tabelas": extraction.get("quantidade_tabelas"),
            "truncado": bool(extraction.get("truncado", False)),
            "artefatos": artifacts,
            "item_conhecimento": {
                **knowledge_item,
                "document_chunk_count": chunk_manifest["chunk_count"],
            },
        }

    def _extract(self, path: Path, extension: str) -> Dict[str, Any]:
        """Seleciona parser sem fallback enganoso para binarios."""

        if extension in _SIMPLE_TEXT_EXTENSIONS:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return {
                    "status": "erro",
                    "metodo": "native_utf8_text",
                    "motivo": "Arquivo textual não é UTF-8 válido; nenhuma decodificação destrutiva foi aplicada.",
                }
            return self._package_native_text(text, "native_utf8_text")

        if extension == "json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                text = json.dumps(data, indent=2, ensure_ascii=False)
                return self._package_native_text(text, "native_json")
            except Exception as exc:
                return {
                    "status": "erro",
                    "metodo": "native_json",
                    "motivo": f"JSON inválido: {exc.__class__.__name__}: {exc}",
                }

        if extension == "csv":
            try:
                with path.open("r", encoding="utf-8", newline="") as stream:
                    reader = csv.reader(stream)
                    text = "\n".join(" | ".join(row) for row in reader)
                return self._package_native_text(text, "native_csv")
            except Exception as exc:
                return {
                    "status": "erro",
                    "metodo": "native_csv",
                    "motivo": f"Falha real ao ler CSV: {exc.__class__.__name__}: {exc}",
                }

        if extension in _DOCLING_EXTENSIONS:
            result = self.document_stack.parse(path)
            if result.get("status") != "sucesso":
                return {
                    **result,
                    "motivo": (
                        result.get("motivo")
                        or f"Docling indisponível para o formato .{extension}."
                    ),
                }
            return result

        return {
            "status": "indisponivel",
            "metodo": None,
            "motivo": (
                f"Formato .{extension or 'desconhecido'} não possui parser confiável configurado. "
                "O Jarvis não tentará ler bytes arbitrários como texto."
            ),
        }

    def _package_native_text(self, text: str, method: str) -> Dict[str, Any]:
        clean = str(text).strip()
        chunks = self.document_stack.chunker.split(clean)
        return {
            "status": "sucesso",
            "metodo": method,
            "texto": clean,
            "markdown": clean,
            "estruturado": None,
            "quantidade_tabelas": None,
            "truncado": False,
            "chunks": chunks,
            "chunk_count": len(chunks),
        }

    def _persist_extraction_artifacts(
        self,
        *,
        path: Path,
        title: str,
        extension: str,
        source_hash: str,
        raw_text: str,
        extraction: Dict[str, Any],
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Mantem uma representacao auditavel da extracao fora do resumo SQLite."""

        safe_stem = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in path.stem
        )[:80] or "documento"
        prefix = f"{safe_stem}_{source_hash[:12]}"
        markdown_path = self.artifact_dir / f"{prefix}.md"
        manifest_path = self.artifact_dir / f"{prefix}.json"

        markdown_path.write_text(raw_text, encoding="utf-8")

        manifest = {
            "schema_version": "1.0",
            "source_name": path.name,
            "source_path": str(path),
            "source_extension": extension,
            "source_sha256": source_hash,
            "title": title,
            "parser": extraction.get("metodo"),
            "text_chars": len(raw_text),
            "chunk_count": len(chunks),
            "table_count": extraction.get("quantidade_tabelas"),
            "truncated": bool(extraction.get("truncado", False)),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "chunks": [
                {
                    "index": int(chunk.get("index", index)),
                    "chars": int(chunk.get("chars", len(str(chunk.get("text", ""))))),
                }
                for index, chunk in enumerate(chunks)
            ],
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "markdown": str(markdown_path),
            "manifest": str(manifest_path),
        }

    def describe_capabilities(self) -> Dict[str, Any]:
        return {
            "simple_text_extensions": sorted(_SIMPLE_TEXT_EXTENSIONS),
            "native_formats": ["json", "csv"],
            "structured_formats": sorted(_DOCLING_EXTENSIONS),
            "document_stack": self.document_stack.status(),
            "artifact_dir": str(self.artifact_dir),
            "binary_string_scraping": False,
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
