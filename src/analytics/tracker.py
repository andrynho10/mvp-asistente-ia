"""
Sistema de tracking de interacciones para analytics.
Registra queries, respuestas, feedback y métricas en SQLite.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import logging

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """Tracker para registrar todas las interacciones del sistema."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Inicializa las tablas de la base de datos."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Tabla de queries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT,
                    num_references INTEGER,
                    metadata_filters TEXT,
                    response_time_ms REAL,
                    session_id TEXT,
                    error TEXT
                )
            """)

            # Tabla de referencias (source documents)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_references (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    chunk_id TEXT,
                    process TEXT,
                    keywords TEXT,
                    FOREIGN KEY (query_id) REFERENCES queries(id)
                )
            """)

            # Tabla de feedback
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id INTEGER,
                    timestamp DATETIME NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    is_helpful BOOLEAN NOT NULL,
                    comment TEXT,
                    FOREIGN KEY (query_id) REFERENCES queries(id)
                )
            """)

            # Índices para mejorar performance de queries analíticas
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_timestamp ON queries(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_helpful ON feedback(is_helpful)")

            conn.commit()
            logger.info(f"Base de datos de analytics inicializada en {self.db_path}")

    def track_query(
        self,
        question: str,
        answer: str,
        references: list[dict[str, Any]],
        metadata_filters: Optional[dict[str, Any]] = None,
        response_time_ms: Optional[float] = None,
        session_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> int:
        """
        Registra una query y sus resultados.

        Returns:
            query_id: ID de la query insertada
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Insertar query
            cursor.execute(
                """
                INSERT INTO queries (
                    timestamp, question, answer, num_references,
                    metadata_filters, response_time_ms, session_id, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    question,
                    answer,
                    len(references),
                    json.dumps(metadata_filters) if metadata_filters else None,
                    response_time_ms,
                    session_id,
                    error,
                ),
            )
            query_id = cursor.lastrowid

            # Insertar referencias
            for ref in references:
                cursor.execute(
                    """
                    INSERT INTO query_references (
                        query_id, source, chunk_id, process, keywords
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        query_id,
                        ref.get("source", ""),
                        ref.get("chunk_id"),
                        ref.get("process"),
                        json.dumps(ref.get("keywords", [])),
                    ),
                )

            conn.commit()
            logger.debug(f"Query tracked con ID {query_id}")
            return query_id

    def track_feedback(
        self,
        question: str,
        answer: str,
        is_helpful: bool,
        comment: Optional[str] = None,
        query_id: Optional[int] = None,
    ) -> int:
        """
        Registra feedback de usuario.

        Returns:
            feedback_id: ID del feedback insertado
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO feedback (
                    query_id, timestamp, question, answer, is_helpful, comment
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    datetime.now().isoformat(),
                    question,
                    answer,
                    is_helpful,
                    comment,
                ),
            )
            feedback_id = cursor.lastrowid
            conn.commit()
            logger.debug(f"Feedback tracked con ID {feedback_id}")
            return feedback_id

    def get_recent_queries(self, limit: int = 100) -> list[dict[str, Any]]:
        """Obtiene las queries más recientes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM queries
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_feedback_stats(self) -> dict[str, Any]:
        """Obtiene estadísticas de feedback."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END) as helpful,
                    SUM(CASE WHEN is_helpful = 0 THEN 1 ELSE 0 END) as not_helpful
                FROM feedback
            """)

            row = cursor.fetchone()
            total, helpful, not_helpful = row

            return {
                "total": total,
                "helpful": helpful,
                "not_helpful": not_helpful,
                "satisfaction_rate": (helpful / total * 100) if total > 0 else 0,
            }
