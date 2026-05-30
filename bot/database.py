import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class DatabaseManager:
    """Gerencia armazenamento de arquivos, correlações e resultados de análise."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    uploader_id TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    analysis_summary TEXT,
                    alerts_count INTEGER DEFAULT 0
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS correlations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    correlation_type TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(file_id) REFERENCES files(id)
                )
                """
            )
            connection.commit()

    def add_file_record(
        self,
        filename: str,
        file_path: str,
        uploader_id: str,
        file_type: str,
        status: str = "received",
    ) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO files (filename, file_path, uploader_id, file_type, status, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    file_path,
                    uploader_id,
                    file_type,
                    status,
                    datetime.utcnow().isoformat(),
                ),
            )
            connection.commit()
            return cursor.lastrowid

    def update_file_analysis(
        self,
        file_id: int,
        analysis_summary: Dict[str, Any],
        alerts_count: int,
    ) -> None:
        payload = json.dumps(analysis_summary, default=str)
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE files
                SET analysis_summary = ?, alerts_count = ?, status = ?
                WHERE id = ?
                """,
                (payload, alerts_count, "analyzed", file_id),
            )
            connection.commit()

    def add_correlation(
        self,
        file_id: int,
        correlation_type: str,
        details: Dict[str, Any],
    ) -> int:
        payload = json.dumps(details, default=str)
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO correlations (file_id, correlation_type, details, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (file_id, correlation_type, payload, datetime.utcnow().isoformat()),
            )
            connection.commit()
            return cursor.lastrowid

    def list_files(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, filename, file_type, status, uploaded_at, alerts_count
                FROM files
                ORDER BY uploaded_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "filename": row[1],
                    "file_type": row[2],
                    "status": row[3],
                    "uploaded_at": row[4],
                    "alerts_count": row[5],
                }
                for row in rows
            ]


class SupportDatabaseManager:
    """Gerencia tickets de suporte e pedidos de análise."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS support_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    request_text TEXT NOT NULL,
                    problem_description TEXT NOT NULL,
                    solution_text TEXT,
                    status TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )
            connection.commit()

    def create_request(
        self,
        user_id: str,
        request_text: str,
        problem_description: str,
    ) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO support_requests (
                    user_id,
                    request_text,
                    problem_description,
                    status,
                    opened_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    request_text,
                    problem_description,
                    "open",
                    datetime.utcnow().isoformat(),
                ),
            )
            connection.commit()
            return cursor.lastrowid

    def resolve_request(self, request_id: int, solution_text: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE support_requests
                SET solution_text = ?, status = ?, resolved_at = ?
                WHERE id = ?
                """,
                (
                    solution_text,
                    "resolved",
                    datetime.utcnow().isoformat(),
                    request_id,
                ),
            )
            connection.commit()
            return cursor.rowcount > 0

    def list_open_requests(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, user_id, request_text, problem_description, status, opened_at
                FROM support_requests
                WHERE status = 'open'
                ORDER BY opened_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "request_text": row[2],
                    "problem_description": row[3],
                    "status": row[4],
                    "opened_at": row[5],
                }
                for row in rows
            ]
