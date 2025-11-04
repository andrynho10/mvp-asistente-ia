"""
Motor de recomendaciones contextuales.
Sugiere contenido relevante basándose en comportamiento histórico y patrones.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import logging

logger = logging.getLogger(__name__)


class Recommender:
    """
    Motor de recomendaciones que sugiere:
    - Preguntas relacionadas ("Usuarios que preguntaron X también preguntaron Y")
    - Documentos relevantes
    - Próximos pasos en flujos comunes
    """

    def __init__(self, analytics_db_path: Path):
        self.db_path = analytics_db_path

    def get_similar_questions(self, question: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Encuentra preguntas similares basándose en palabras clave.

        Args:
            question: Pregunta de referencia
            limit: Número máximo de sugerencias

        Returns:
            Lista de preguntas similares con frecuencia
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Extraer palabras clave de la pregunta (simplificado)
            keywords = [
                word.lower()
                for word in question.split()
                if len(word) > 3 and word.lower() not in ["cuál", "cómo", "dónde", "cuándo", "quién", "para"]
            ]

            if not keywords:
                return []

            # Buscar preguntas con palabras clave similares
            similar = []
            for keyword in keywords[:3]:  # Usar las primeras 3 palabras clave
                cursor.execute(
                    """
                    SELECT question, COUNT(*) as frequency
                    FROM queries
                    WHERE LOWER(question) LIKE ?
                      AND LOWER(question) != LOWER(?)
                      AND error IS NULL
                    GROUP BY LOWER(question)
                    ORDER BY frequency DESC
                    LIMIT ?
                    """,
                    (f"%{keyword}%", question, limit),
                )
                similar.extend(cursor.fetchall())

            # Deduplicar y ordenar por frecuencia
            seen = set()
            unique_questions = []
            for q, freq in similar:
                if q.lower() not in seen:
                    seen.add(q.lower())
                    unique_questions.append({"question": q, "frequency": freq})

            return unique_questions[:limit]

    def get_collaborative_recommendations(
        self, current_question: str, limit: int = 3, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        "Usuarios que preguntaron X también preguntaron Y"
        Basado en co-ocurrencia en sesiones.

        Args:
            current_question: Pregunta actual del usuario
            limit: Número de recomendaciones
            days: Período a considerar

        Returns:
            Lista de preguntas recomendadas
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            # Encontrar sesiones que contienen preguntas similares
            keywords = [
                word.lower()
                for word in current_question.split()
                if len(word) > 3 and word.lower() not in ["cuál", "cómo", "dónde", "cuándo", "quién"]
            ]

            if not keywords:
                return []

            # Buscar sesiones relacionadas
            cursor.execute(
                """
                SELECT DISTINCT session_id
                FROM queries
                WHERE LOWER(question) LIKE ?
                  AND session_id IS NOT NULL
                  AND timestamp >= ?
                """,
                (f"%{keywords[0]}%", date_limit),
            )

            session_ids = [row[0] for row in cursor.fetchall() if row[0]]

            if not session_ids:
                return []

            # Encontrar otras preguntas en esas sesiones
            placeholders = ",".join("?" * len(session_ids))
            cursor.execute(
                f"""
                SELECT question, COUNT(*) as co_occurrence
                FROM queries
                WHERE session_id IN ({placeholders})
                  AND LOWER(question) NOT LIKE ?
                  AND timestamp >= ?
                GROUP BY LOWER(question)
                ORDER BY co_occurrence DESC
                LIMIT ?
                """,
                (*session_ids, f"%{keywords[0]}%", date_limit, limit),
            )

            return [
                {"question": row[0], "co_occurrence_count": row[1], "relevance": "high"}
                for row in cursor.fetchall()
            ]

    def suggest_next_steps(self, current_topic: str, limit: int = 3) -> list[dict[str, Any]]:
        """
        Sugiere próximos pasos basándose en flujos comunes.

        Args:
            current_topic: Tema/proceso actual
            limit: Número de sugerencias

        Returns:
            Lista de próximos pasos sugeridos
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Encontrar temas que frecuentemente siguen al tema actual
            cursor.execute(
                """
                WITH topic_sequences AS (
                    SELECT
                        q1.id as first_query,
                        q2.id as second_query,
                        qr2.process as next_topic
                    FROM queries q1
                    JOIN queries q2 ON q1.session_id = q2.session_id
                    JOIN query_references qr1 ON q1.id = qr1.query_id
                    JOIN query_references qr2 ON q2.id = qr2.query_id
                    WHERE qr1.process = ?
                      AND q2.timestamp > q1.timestamp
                      AND qr2.process != qr1.process
                      AND q1.session_id IS NOT NULL
                )
                SELECT next_topic, COUNT(*) as frequency
                FROM topic_sequences
                GROUP BY next_topic
                ORDER BY frequency DESC
                LIMIT ?
                """,
                (current_topic, limit),
            )

            return [
                {
                    "suggested_topic": row[0],
                    "reason": f"Usuarios que consultaron '{current_topic}' frecuentemente continúan con este tema",
                    "frequency": row[1],
                }
                for row in cursor.fetchall()
            ]

    def get_trending_content(self, days: int = 7, limit: int = 5) -> list[dict[str, Any]]:
        """
        Identifica contenido trending (más consultado recientemente).

        Args:
            days: Período a considerar
            limit: Número de items

        Returns:
            Lista de contenido trending
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT qr.source, qr.process, COUNT(*) as recent_views
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE q.timestamp >= ?
                GROUP BY qr.source
                ORDER BY recent_views DESC
                LIMIT ?
                """,
                (date_limit, limit),
            )

            return [
                {
                    "source": row[0],
                    "process": row[1],
                    "views_last_{}_days".format(days): row[2],
                    "status": "trending",
                }
                for row in cursor.fetchall()
            ]

    def recommend_for_topic(
        self, topic: str, user_context: dict[str, Any] | None = None, limit: int = 5
    ) -> dict[str, Any]:
        """
        Genera recomendaciones completas para un tema específico.

        Args:
            topic: Tema/proceso de interés
            user_context: Contexto adicional del usuario (opcional)
            limit: Número de recomendaciones por categoría

        Returns:
            Dict con múltiples tipos de recomendaciones
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            recommendations = {
                "topic": topic,
                "popular_questions": [],
                "related_topics": [],
                "key_documents": [],
            }

            # Preguntas populares sobre el tema
            cursor.execute(
                """
                SELECT q.question, COUNT(*) as frequency
                FROM queries q
                JOIN query_references qr ON q.id = qr.query_id
                WHERE qr.process = ?
                  AND q.error IS NULL
                GROUP BY LOWER(q.question)
                ORDER BY frequency DESC
                LIMIT ?
                """,
                (topic, limit),
            )
            recommendations["popular_questions"] = [
                {"question": row[0], "asked_times": row[1]} for row in cursor.fetchall()
            ]

            # Temas relacionados (co-ocurrencia)
            cursor.execute(
                """
                SELECT qr2.process, COUNT(*) as co_occurrence
                FROM query_references qr1
                JOIN query_references qr2 ON qr1.query_id = qr2.query_id
                WHERE qr1.process = ?
                  AND qr2.process != ?
                  AND qr2.process IS NOT NULL
                GROUP BY qr2.process
                ORDER BY co_occurrence DESC
                LIMIT ?
                """,
                (topic, topic, limit),
            )
            recommendations["related_topics"] = [
                {"topic": row[0], "relevance_score": row[1]} for row in cursor.fetchall()
            ]

            # Documentos clave
            cursor.execute(
                """
                SELECT qr.source, COUNT(*) as references
                FROM query_references qr
                WHERE qr.process = ?
                GROUP BY qr.source
                ORDER BY references DESC
                LIMIT ?
                """,
                (topic, limit),
            )
            recommendations["key_documents"] = [
                {"source": row[0], "reference_count": row[1]} for row in cursor.fetchall()
            ]

            return recommendations

    def get_personalized_suggestions(
        self, session_history: list[str], limit: int = 3
    ) -> list[dict[str, Any]]:
        """
        Genera sugerencias personalizadas basándose en el historial de la sesión.

        Args:
            session_history: Lista de preguntas previas en la sesión
            limit: Número de sugerencias

        Returns:
            Lista de sugerencias personalizadas
        """
        if not session_history:
            return []

        # Extraer temas de las preguntas previas
        topics_of_interest = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for question in session_history[-3:]:  # Considerar últimas 3 preguntas
                cursor.execute(
                    """
                    SELECT DISTINCT qr.process
                    FROM queries q
                    JOIN query_references qr ON q.id = qr.query_id
                    WHERE LOWER(q.question) = LOWER(?)
                    LIMIT 1
                    """,
                    (question,),
                )
                result = cursor.fetchone()
                if result:
                    topics_of_interest.append(result[0])

        if not topics_of_interest:
            return []

        # Sugerir próximos pasos basados en los temas de interés
        suggestions = []
        for topic in topics_of_interest:
            next_steps = self.suggest_next_steps(topic, limit=1)
            suggestions.extend(next_steps)

        # Deduplicar
        seen = set()
        unique_suggestions = []
        for sug in suggestions:
            if sug["suggested_topic"] not in seen:
                seen.add(sug["suggested_topic"])
                unique_suggestions.append(sug)

        return unique_suggestions[:limit]
