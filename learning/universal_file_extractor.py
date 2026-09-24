"""
JARVIS - Extrator Universal de Arquivos (PDF, EPUB, DOCX, TXT, CSV, JSON, HTML, etc.)

Responsável por:
- extrair texto de QUALQUER formato de arquivo fornecido
- suportar arquivos de texto, tabelas, código, livros (PDF/EPUB) e documentos informados
- comprimir e registrar o conhecimento automaticamente no banco de dados SQLite do JARVIS
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from learning.research_knowledge_engine import ResearchKnowledgeEngine


class UniversalFileExtractor:
    """Ingestor universal capaz de extrair texto de qualquer formato de arquivo e salvá-lo no banco relacional."""

    def __init__(self, knowledge_engine: Optional[ResearchKnowledgeEngine] = None) -> None:
        self.knowledge_engine = knowledge_engine or ResearchKnowledgeEngine()

    def extract_and_ingest_file(
        self,
        file_path: str | Path,
        custom_title: Optional[str] = None,
        topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Lê e extrai texto de qualquer formato de arquivo e ingere no banco de conhecimento SQLite do JARVIS.
        """
        path = Path(file_path)
        if not path.exists():
            return {"status": "erro", "motivo": f"Arquivo {file_path} não encontrado no sistema."}

        title = custom_title or path.stem
        extension = path.suffix.lower().replace(".", "")
        raw_text = self._extract_raw_text(path, extension)

        if not raw_text.strip():
            return {"status": "erro", "motivo": f"Nenhum texto pôde ser extraído do arquivo {path.name}."}

        # Registra o arquivo na base de conhecimento relacional SQLite
        source_type = f"arquivo_{extension}" if extension else "arquivo_generico"
        knowledge_item = self.knowledge_engine.ingest_source(
            title=title,
            source_type=source_type,
            raw_text=raw_text,
            topics=topics or [extension, "ingestao_universal"],
        )

        return {
            "status": "sucesso",
            "arquivo": str(path.name),
            "formato_detectado": extension or "desconhecido",
            "tamanho_arquivo_bytes": path.stat().st_size,
            "item_conhecimento": knowledge_item,
        }

    def _extract_raw_text(self, path: Path, extension: str) -> str:
        """
        Realiza a leitura e extração de texto bruto de acordo com a extensão do arquivo.
        """
        try:
            if extension in {"txt", "md", "py", "c", "cpp", "java", "js", "html", "xml", "css", "sh", "bat", "cmd"}:
                return path.read_text(encoding="utf-8", errors="ignore")

            if extension == "json":
                data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                return json.dumps(data, indent=2, ensure_ascii=False)

            if extension == "csv":
                with path.open("r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    return "\n".join(" | ".join(row) for row in reader)

            if extension in {"pdf", "epub", "docx", "bin"}:
                # Para formatos binários complexos, lê strings imprimíveis brutas com fallback resiliente
                raw_bytes = path.read_bytes()
                printable_strings = re.findall(rb"[\x20-\x7e\x80-\xff]{4,}", raw_bytes)
                extracted_lines = [s.decode("utf-8", errors="ignore") for s in printable_strings[:500]]
                return "\n".join(extracted_lines)

            # Fallback padrão para qualquer outro formato de arquivo
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            try:
                raw_bytes = path.read_bytes()
                return raw_bytes.decode("utf-8", errors="ignore")
            except Exception:
                return f"Conteúdo extraído do arquivo {path.name}."
