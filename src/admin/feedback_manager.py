"""
Gestor de feedback para revisión y gestión de feedback del usuario.
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FeedbackManager:
    """Gestor de feedback con capacidad de revisión y categorización."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Obtiene conexión a la base de datos."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_negative_feedback(
        self, days: int = 30, category: Optional[str] = None, status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Obtiene feedback negativo para revisión.

        Args:
            days: Días hacia atrás a consultar
            category: Filtrar por categoría (opcional)
            status: Filtrar por estado (pending, reviewed, actioned)

        Returns:
            Lista de feedback negativo
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        since_date = (datetime.now() - timedelta(days=days)).isoformat()

        query = """
            SELECT f.*, q.question
            FROM feedback f
            JOIN queries q ON f.query_id = q.id
            WHERE f.is_helpful = 0
            AND f.timestamp >= ?
        """

        params = [since_date]

        if category:
            query += " AND f.category = ?"
            params.append(category)

        if status:
            query += " AND f.status = ?"
            params.append(status)

        query += " ORDER BY f.timestamp DESC"

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()

            feedbacks = []
            for row in rows:
                feedbacks.append(
                    {
                        "id": row["id"],
                        "query_id": row["query_id"],
                        "question": row["question"],
                        "comment": row["comment"],
                        "timestamp": row["timestamp"],
                        "category": row["category"],
                        "status": row["status"],
                        "action_notes": row["action_notes"],
                    }
                )
            return feedbacks
        except Exception as e:
            logger.error(f"Error al obtener feedback negativo: {e}")
            return []
        finally:
            conn.close()

    def categorize_feedback(self, feedback_id: int, category: str) -> None:
        """
        Categoriza un feedback.

        Args:
            feedback_id: ID del feedback
            category: Categoría (missing_info, incorrect_answer, unclear, other)
        """
        valid_categories = ["missing_info", "incorrect_answer", "unclear", "other"]
        if category not in valid_categories:
            raise ValueError(
                f"Categoría inválida: {category}. Válidas: {', '.join(valid_categories)}"
            )

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE feedback
                SET category = ?, status = 'reviewed'
                WHERE id = ?
            """,
                (category, feedback_id),
            )
            conn.commit()
            logger.info(f"Feedback {feedback_id} categorizado como: {category}")
        except Exception as e:
            logger.error(f"Error al categorizar feedback: {e}")
            conn.rollback()
        finally:
            conn.close()

    def mark_as_actioned(self, feedback_id: int, action_notes: str) -> None:
        """
        Marca un feedback como accionado.

        Args:
            feedback_id: ID del feedback
            action_notes: Notas sobre la acción tomada
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE feedback
                SET status = 'actioned', action_notes = ?
                WHERE id = ?
            """,
                (action_notes, feedback_id),
            )
            conn.commit()
            logger.info(f"Feedback {feedback_id} marcado como accionado")
        except Exception as e:
            logger.error(f"Error al marcar feedback como accionado: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_feedback_stats(self, days: int = 30) -> dict[str, Any]:
        """
        Obtiene estadísticas de feedback.

        Args:
            days: Días hacia atrás a analizar

        Returns:
            Estadísticas de feedback
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        since_date = (datetime.now() - timedelta(days=days)).isoformat()

        try:
            # Total feedback
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_helpful = 0 THEN 1 ELSE 0 END) as negative,
                    SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END) as positive
                FROM feedback
                WHERE timestamp >= ?
            """,
                (since_date,),
            )
            totals = cursor.fetchone()

            # Por categoría
            cursor.execute(
                """
                SELECT category, COUNT(*) as count
                FROM feedback
                WHERE timestamp >= ? AND is_helpful = 0 AND category IS NOT NULL
                GROUP BY category
            """,
                (since_date,),
            )
            by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

            # Por estado
            cursor.execute(
                """
                SELECT status, COUNT(*) as count
                FROM feedback
                WHERE timestamp >= ? AND is_helpful = 0
                GROUP BY status
            """,
                (since_date,),
            )
            by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

            return {
                "total_feedback": totals["total"] or 0,
                "negative_feedback": totals["negative"] or 0,
                "positive_feedback": totals["positive"] or 0,
                "by_category": by_category,
                "by_status": by_status,
                "pending_review": by_status.get("pending", 0),
                "actioned": by_status.get("actioned", 0),
            }
        except Exception as e:
            logger.error(f"Error al calcular estadísticas de feedback: {e}")
            return {
                "total_feedback": 0,
                "negative_feedback": 0,
                "positive_feedback": 0,
                "by_category": {},
                "by_status": {},
                "pending_review": 0,
                "actioned": 0,
            }
        finally:
            conn.close()

    def get_top_issues(self, days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
        """
        Obtiene los temas con más feedback negativo.

        Args:
            days: Días hacia atrás a analizar
            limit: Número máximo de resultados

        Returns:
            Lista de temas con feedback negativo
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        since_date = (datetime.now() - timedelta(days=days)).isoformat()

        try:
            cursor.execute(
                """
                SELECT
                    qr.process as topic,
                    COUNT(*) as negative_count,
                    COUNT(DISTINCT f.query_id) as affected_queries
                FROM feedback f
                JOIN queries q ON f.query_id = q.id
                JOIN query_references qr ON q.id = qr.query_id
                WHERE f.is_helpful = 0
                AND f.timestamp >= ?
                AND qr.process IS NOT NULL
                GROUP BY qr.process
                ORDER BY negative_count DESC
                LIMIT ?
            """,
                (since_date, limit),
            )

            issues = []
            for row in cursor.fetchall():
                issues.append(
                    {
                        "topic": row["topic"],
                        "negative_count": row["negative_count"],
                        "affected_queries": row["affected_queries"],
                    }
                )
            return issues
        except Exception as e:
            logger.error(f"Error al obtener top issues: {e}")
            return []
        finally:
            conn.close()
