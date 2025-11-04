"""
Analizador de patrones en consultas y comportamiento de usuarios.
Identifica tendencias, gaps de conocimiento y temas emergentes.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import logging

logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """
    Analiza patrones en el uso del sistema para identificar:
    - Temas emergentes
    - Gaps de conocimiento
    - Horarios pico de uso
    - Consultas relacionadas
    """

    def __init__(self, analytics_db_path: Path):
        self.db_path = analytics_db_path

    def get_emerging_topics(self, days: int = 7, threshold: float = 1.5) -> list[dict[str, Any]]:
        """
        Identifica temas con crecimiento acelerado en consultas.

        Args:
            days: Período a analizar
            threshold: Factor de crecimiento mínimo (1.5 = 50% más consultas que promedio)

        Returns:
            Lista de temas emergentes con tasa de crecimiento
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Calcular fecha límite
            date_limit = (datetime.now() - timedelta(days=days)).isoformat()
            midpoint = (datetime.now() - timedelta(days=days // 2)).isoformat()

            # Consultas por tema en primera mitad del período
            cursor.execute(
                """
                SELECT qr.process, COUNT(*) as count
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE q.timestamp >= ? AND q.timestamp < ? AND qr.process IS NOT NULL
                GROUP BY qr.process
                """,
                (date_limit, midpoint),
            )
            first_half = {row[0]: row[1] for row in cursor.fetchall()}

            # Consultas por tema en segunda mitad del período
            cursor.execute(
                """
                SELECT qr.process, COUNT(*) as count
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE q.timestamp >= ? AND qr.process IS NOT NULL
                GROUP BY qr.process
                """,
                (midpoint,),
            )
            second_half = {row[0]: row[1] for row in cursor.fetchall()}

            # Calcular crecimiento
            emerging = []
            for topic in second_half:
                count_recent = second_half[topic]
                count_old = first_half.get(topic, 0)

                if count_old == 0:
                    # Tema nuevo
                    growth_rate = float("inf")
                else:
                    growth_rate = count_recent / count_old

                if growth_rate >= threshold:
                    emerging.append(
                        {
                            "topic": topic,
                            "recent_queries": count_recent,
                            "previous_queries": count_old,
                            "growth_rate": round(growth_rate, 2),
                            "is_new": count_old == 0,
                        }
                    )

            # Ordenar por tasa de crecimiento
            emerging.sort(key=lambda x: x["growth_rate"], reverse=True)
            return emerging

    def detect_knowledge_gaps(self, days: int = 7, min_queries: int = 3) -> list[dict[str, Any]]:
        """
        Identifica temas con muchas consultas pero baja satisfacción o sin referencias.

        Args:
            days: Período a analizar
            min_queries: Mínimo de consultas para considerar un gap

        Returns:
            Lista de temas con gaps de conocimiento
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            # Temas con muchas consultas sin referencias
            cursor.execute(
                """
                SELECT qr.process, COUNT(*) as query_count,
                       SUM(CASE WHEN q.num_references = 0 THEN 1 ELSE 0 END) as no_ref_count
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE q.timestamp >= ? AND qr.process IS NOT NULL
                GROUP BY qr.process
                HAVING query_count >= ?
                """,
                (date_limit, min_queries),
            )

            gaps = []
            for row in cursor.fetchall():
                topic, query_count, no_ref_count = row
                gap_rate = (no_ref_count / query_count) * 100

                if gap_rate > 20:  # Más del 20% sin referencias
                    gaps.append(
                        {
                            "topic": topic,
                            "query_count": query_count,
                            "queries_without_references": no_ref_count,
                            "gap_rate": round(gap_rate, 2),
                            "severity": "high" if gap_rate > 50 else "medium",
                        }
                    )

            # Ordenar por severidad
            gaps.sort(key=lambda x: x["gap_rate"], reverse=True)
            return gaps

    def get_peak_usage_hours(self, days: int = 30) -> list[dict[str, Any]]:
        """
        Identifica las horas del día con mayor actividad.

        Args:
            days: Período a analizar

        Returns:
            Lista de horas con conteo de consultas
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT
                    CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                    COUNT(*) as count
                FROM queries
                WHERE timestamp >= ?
                GROUP BY hour
                ORDER BY count DESC
                """,
                (date_limit,),
            )

            return [{"hour": row[0], "query_count": row[1]} for row in cursor.fetchall()]

    def find_related_queries(
        self, query: str, limit: int = 5, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Encuentra consultas relacionadas basándose en co-ocurrencia de temas.

        Args:
            query: Consulta de referencia
            limit: Número máximo de consultas relacionadas
            days: Período a considerar

        Returns:
            Lista de consultas relacionadas con score de relevancia
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            # Encontrar temas de la query de referencia
            cursor.execute(
                """
                SELECT DISTINCT qr.process
                FROM queries q
                JOIN query_references qr ON q.id = qr.query_id
                WHERE q.question LIKE ? AND q.timestamp >= ? AND qr.process IS NOT NULL
                LIMIT 3
                """,
                (f"%{query}%", date_limit),
            )

            reference_topics = [row[0] for row in cursor.fetchall()]

            if not reference_topics:
                return []

            # Buscar queries que comparten esos temas
            placeholders = ",".join("?" * len(reference_topics))
            cursor.execute(
                f"""
                SELECT q.question, COUNT(DISTINCT qr.process) as shared_topics, COUNT(*) as frequency
                FROM queries q
                JOIN query_references qr ON q.id = qr.query_id
                WHERE qr.process IN ({placeholders})
                  AND q.timestamp >= ?
                  AND q.question NOT LIKE ?
                GROUP BY q.question
                ORDER BY shared_topics DESC, frequency DESC
                LIMIT ?
                """,
                (*reference_topics, date_limit, f"%{query}%", limit),
            )

            return [
                {
                    "question": row[0],
                    "shared_topics": row[1],
                    "frequency": row[2],
                    "relevance_score": round((row[1] / len(reference_topics)) * 100, 2),
                }
                for row in cursor.fetchall()
            ]

    def get_underutilized_content(self, days: int = 30) -> list[dict[str, Any]]:
        """
        Identifica documentos que existen pero son raramente consultados.

        Args:
            days: Período a analizar

        Returns:
            Lista de documentos subutilizados
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            # Documentos con pocas referencias
            cursor.execute(
                """
                SELECT qr.source, qr.process, COUNT(*) as reference_count
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE q.timestamp >= ?
                GROUP BY qr.source
                HAVING reference_count < 3
                ORDER BY reference_count ASC
                LIMIT 10
                """,
                (date_limit,),
            )

            return [
                {"source": row[0], "process": row[1], "reference_count": row[2]}
                for row in cursor.fetchall()
            ]

    def predict_future_volume(self, days_ahead: int = 7, historical_days: int = 30) -> dict[str, Any]:
        """
        Predice volumen futuro de consultas basándose en tendencia histórica.

        Args:
            days_ahead: Días a predecir
            historical_days: Días históricos para calcular tendencia

        Returns:
            Predicción de volumen con rango de confianza
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=historical_days)).isoformat()

            # Consultas por día en período histórico
            cursor.execute(
                """
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM queries
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
                """,
                (date_limit,),
            )

            daily_counts = [row[1] for row in cursor.fetchall()]

            if len(daily_counts) < 7:
                return {
                    "prediction": None,
                    "message": "Datos insuficientes para predicción (mínimo 7 días)",
                }

            # Cálculo simple: promedio de últimos N días con ajuste de tendencia
            recent_avg = sum(daily_counts[-7:]) / 7
            overall_avg = sum(daily_counts) / len(daily_counts)
            trend_factor = recent_avg / overall_avg if overall_avg > 0 else 1

            predicted_daily = recent_avg * trend_factor
            predicted_total = predicted_daily * days_ahead

            return {
                "predicted_daily_average": round(predicted_daily, 1),
                "predicted_total_next_{}_days".format(days_ahead): round(predicted_total, 0),
                "trend": "creciente" if trend_factor > 1.1 else "estable" if trend_factor > 0.9 else "decreciente",
                "confidence": "medium",  # Simplificado, podría usar desviación estándar
            }
