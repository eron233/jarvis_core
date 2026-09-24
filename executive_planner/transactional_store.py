"""
JARVIS - Armazenamento Transacional SQLite

Responsável por:
- fornecer persistência relacional transacional e atômica via SQLite (WAL mode)
- armazenar fila de tarefas, auditoria e eventos com garantia ACID
- oferecer sincronização transparente e fallback seguro para JSON
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "jarvis_transactional.db"


class TransactionalStore:
    """Motor SQLite transacional para Fila de Tarefas e Auditoria."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._lock = RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Cria conexao SQLite com WAL ativado."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Inicializa as tabelas necessarias."""
        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS task_queue (
                        task_id TEXT PRIMARY KEY,
                        domain TEXT,
                        state TEXT,
                        priority INTEGER,
                        created_at TEXT,
                        updated_at TEXT,
                        payload_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT,
                        event_type TEXT,
                        actor TEXT,
                        timestamp TEXT,
                        details_json TEXT
                    )
                    """
                )
                conn.commit()

    # --- Operações para Fila de Tarefas ---

    def save_queue_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """Salva a lista completa de tarefas na tabela transacional."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("BEGIN TRANSACTION;")
                conn.execute("DELETE FROM task_queue;")
                for task in tasks:
                    t_id = str(task.get("task_id", task.get("id", "")))
                    domain = str(task.get("domain", "general"))
                    state = str(task.get("state", "queued"))
                    priority = int(task.get("urgency", 0))
                    created_at = str(task.get("created_at", ""))
                    updated_at = str(task.get("updated_at", ""))
                    payload = json.dumps(task, ensure_ascii=False)
                    conn.execute(
                        """
                        INSERT INTO task_queue (task_id, domain, state, priority, created_at, updated_at, payload_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (t_id, domain, state, priority, created_at, updated_at, payload),
                    )
                conn.commit()

    def load_queue_tasks(self) -> List[Dict[str, Any]]:
        """Carrega todas as tarefas da tabela transacional."""
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT payload_json FROM task_queue ORDER BY rowid ASC;").fetchall()
                tasks = []
                for row in rows:
                    try:
                        tasks.append(json.loads(row["payload_json"]))
                    except Exception:
                        pass
                return tasks

    # --- Operações para Auditoria ---

    def append_audit_event(self, event: Dict[str, Any]) -> None:
        """Insere um evento de auditoria de forma atômica."""
        with self._lock:
            e_id = str(event.get("event_id", event.get("id", "")))
            e_type = str(event.get("event", event.get("event_type", "unknown")))
            actor = str(event.get("actor", event.get("device_id", "system")))
            ts = str(event.get("timestamp", ""))
            payload = json.dumps(event, ensure_ascii=False)
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_logs (event_id, event_type, actor, timestamp, details_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (e_id, e_type, actor, ts, payload),
                )
                conn.commit()

    def load_audit_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Carrega os ultimos N eventos de auditoria."""
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT details_json FROM audit_logs ORDER BY id DESC LIMIT ?;", (limit,)
                ).fetchall()
                events = []
                for row in rows:
                    try:
                        events.append(json.loads(row["details_json"]))
                    except Exception:
                        pass
                return events[::-1] # Retorna em ordem cronologica

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas do banco transacional."""
        with self._lock:
            with self._get_connection() as conn:
                q_count = conn.execute("SELECT COUNT(*) FROM task_queue;").fetchone()[0]
                a_count = conn.execute("SELECT COUNT(*) FROM audit_logs;").fetchone()[0]
                return {
                    "tipo": "SQLite",
                    "modo": "WAL",
                    "db_path": str(self.db_path),
                    "total_tarefas_transacionais": q_count,
                    "total_eventos_auditoria_transacionais": a_count,
                }
