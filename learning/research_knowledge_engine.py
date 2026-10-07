"""
JARVIS - Módulo 3: Pesquisa e Conhecimento (Base Intelectual com SQLite)

Responsável por:
- aquisição, ingestão e organização de conhecimento de fontes diversas (blogs, artigos, livros, arquivos/ANA)
- armazenamento relacional em banco SQLite para suporte a grandes volumes de dados sem estourar memória
- compressão semântica e sumarização para redução de espaço de armazenamento
- busca por palavras-chave e tópicos
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge_base"
DEFAULT_KNOWLEDGE_DB = DEFAULT_KNOWLEDGE_DIR / "knowledge_store.db"


class ResearchKnowledgeEngine:
    """Motor de pesquisa, ingestão, compressão semântica e gestão do conhecimento relacional."""

    def __init__(
        self,
        knowledge_dir: Optional[Path] = None,
        db_path: Optional[Path] = None,
    ) -> None:
        self.knowledge_dir = Path(knowledge_dir) if knowledge_dir else DEFAULT_KNOWLEDGE_DIR
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path) if db_path else DEFAULT_KNOWLEDGE_DB
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Abre conexão SQLite com row_factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Inicializa a tabela relacional de conhecimento."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    item_id TEXT PRIMARY KEY,
                    titulo TEXT,
                    tipo_fonte TEXT,
                    topicos_json TEXT,
                    tamanho_original_chars INTEGER,
                    tamanho_comprimido_chars INTEGER,
                    taxa_compressao_pct REAL,
                    resumo_semantico_comprimido TEXT,
                    ingestao_em TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    conteudo TEXT NOT NULL,
                    tamanho_chars INTEGER NOT NULL,
                    source_path TEXT,
                    source_sha256 TEXT,
                    ingestao_em TEXT NOT NULL,
                    FOREIGN KEY(item_id) REFERENCES knowledge_items(item_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_chunks_item
                ON document_chunks(item_id, chunk_index)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_chunks_sha
                ON document_chunks(source_sha256)
                """
            )
            conn.commit()

    def ingest_source(
        self,
        title: str,
        source_type: str,  # "livro", "artigo", "blog", "arquivo_ana"
        raw_text: str,
        topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingere uma nova fonte de conhecimento, realizando compressão semântica e gravação atômica em banco.
        """
        now = datetime.now(timezone.utc).isoformat()
        original_size = len(raw_text)

        compressed_summary = self._compress_content(raw_text)
        compressed_size = len(compressed_summary)
        compression_ratio = round((1 - (compressed_size / max(original_size, 1))) * 100, 2)

        import uuid
        item_id = f"know_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}"
        topics_list = topics or ["geral"]
        topics_json = json.dumps(topics_list, ensure_ascii=False)

        knowledge_item = {
            "item_id": item_id,
            "titulo": title,
            "tipo_fonte": source_type,
            "topicos": topics_list,
            "tamanho_original_chars": original_size,
            "tamanho_comprimido_chars": compressed_size,
            "taxa_compressao_pct": compression_ratio,
            "resumo_semantico_comprimido": compressed_summary,
            "ingestao_em": now,
        }

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_items (
                    item_id, titulo, tipo_fonte, topicos_json,
                    tamanho_original_chars, tamanho_comprimido_chars,
                    taxa_compressao_pct, resumo_semantico_comprimido, ingestao_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id, title, source_type, topics_json,
                    original_size, compressed_size,
                    compression_ratio, compressed_summary, now
                ),
            )
            conn.commit()

        return knowledge_item


    def ingest_document_chunks(
        self,
        item_id: str,
        chunks: List[Dict[str, Any]],
        source_path: Optional[str] = None,
        source_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persiste o conteúdo integral chunkado de um documento extraído."""

        now = datetime.now(timezone.utc).isoformat()
        normalized = []
        for index, chunk in enumerate(chunks):
            text = str(chunk.get("text", "")).strip()
            if not text:
                continue
            chunk_index = int(chunk.get("index", index))
            normalized.append(
                (
                    f"{item_id}:chunk:{chunk_index:06d}",
                    item_id,
                    chunk_index,
                    text,
                    len(text),
                    source_path,
                    source_sha256,
                    now,
                )
            )

        with self._get_connection() as conn:
            conn.execute("DELETE FROM document_chunks WHERE item_id = ?", (item_id,))
            if normalized:
                conn.executemany(
                    """
                    INSERT INTO document_chunks (
                        chunk_id, item_id, chunk_index, conteudo, tamanho_chars,
                        source_path, source_sha256, ingestao_em
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    normalized,
                )
            conn.commit()

        return {
            "item_id": item_id,
            "chunk_count": len(normalized),
            "source_path": source_path,
            "source_sha256": source_sha256,
        }

    def get_document_chunks(self, item_id: str) -> List[Dict[str, Any]]:
        """Recupera todos os chunks de um documento na ordem original."""

        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM document_chunks
                WHERE item_id = ?
                ORDER BY chunk_index ASC
                """,
                (item_id,),
            ).fetchall()
        return [
            {
                "chunk_id": row["chunk_id"],
                "item_id": row["item_id"],
                "chunk_index": row["chunk_index"],
                "conteudo": row["conteudo"],
                "tamanho_chars": row["tamanho_chars"],
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "ingestao_em": row["ingestao_em"],
            }
            for row in rows
        ]

    def search_document_chunks(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Busca textual simples no conteúdo integral preservado dos documentos."""

        clean = str(query).strip().lower()
        if not clean:
            return []
        pattern = f"%{clean}%"
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM document_chunks
                WHERE LOWER(conteudo) LIKE ?
                ORDER BY item_id, chunk_index
                LIMIT ?
                """,
                (pattern, max(1, int(limit))),
            ).fetchall()
        return [
            {
                "chunk_id": row["chunk_id"],
                "item_id": row["item_id"],
                "chunk_index": row["chunk_index"],
                "conteudo": row["conteudo"],
                "tamanho_chars": row["tamanho_chars"],
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "ingestao_em": row["ingestao_em"],
            }
            for row in rows
        ]

    def search_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """Busca conteúdos e conceitos na base de conhecimento SQLite."""
        if not query.strip():
            return self.list_all_knowledge()

        query_like = f"%{query.strip().lower()}%"
        results = []
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM knowledge_items
                WHERE LOWER(titulo) LIKE ?
                   OR LOWER(resumo_semantico_comprimido) LIKE ?
                   OR LOWER(topicos_json) LIKE ?
                """,
                (query_like, query_like, query_like),
            ).fetchall()

            for row in rows:
                results.append(self._row_to_dict(row))

        return results

    def list_all_knowledge(self) -> List[Dict[str, Any]]:
        """Lista todo o catálogo de conhecimento arquivado no banco."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM knowledge_items ORDER BY rowid DESC;").fetchall()
            return [self._row_to_dict(row) for row in rows]

    def _compress_content(self, text: str) -> str:
        """Sintetiza e comprime semanticamente o texto eliminando redundâncias."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return "Conteúdo vazio."
        core_ideas = lines[:min(5, len(lines))]
        return " | ".join(core_ideas)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Converte uma linha da tabela em dicionário Python."""
        try:
            topics = json.loads(row["topicos_json"])
        except Exception:
            topics = ["geral"]

        return {
            "item_id": row["item_id"],
            "titulo": row["titulo"],
            "tipo_fonte": row["tipo_fonte"],
            "topicos": topics,
            "tamanho_original_chars": row["tamanho_original_chars"],
            "tamanho_comprimido_chars": row["tamanho_comprimido_chars"],
            "taxa_compressao_pct": row["taxa_compressao_pct"],
            "resumo_semantico_comprimido": row["resumo_semantico_comprimido"],
            "ingestao_em": row["ingestao_em"],
        }
