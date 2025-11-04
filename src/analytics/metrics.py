"""
Calculador de métricas y analytics avanzados.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import logging

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calcula métricas y estadísticas del sistema."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def get_query_volume_stats(self, days: int = 7) -> dict[str, Any]:
        """Obtiene estadísticas de volumen de queries en los últimos N días."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Calcular fecha límite
            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            # Total de queries
            cursor.execute(
                "SELECT COUNT(*) FROM queries WHERE timestamp >= ?",
                (date_limit,),
            )
            total_queries = cursor.fetchone()[0]

            # Queries por día
            cursor.execute(
                """
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM queries
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                """,
                (date_limit,),
            )
            queries_per_day = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]

            # Promedio de queries por día
            avg_per_day = total_queries / days if days > 0 else 0

            return {
                "total_queries": total_queries,
                "queries_per_day": queries_per_day,
                "avg_queries_per_day": round(avg_per_day, 2),
                "period_days": days,
            }

    def get_top_questions(self, limit: int = 10, days: int = 7) -> list[dict[str, Any]]:
        """Obtiene las preguntas más frecuentes."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT question, COUNT(*) as count
                FROM queries
                WHERE timestamp >= ? AND error IS NULL
                GROUP BY LOWER(TRIM(question))
                ORDER BY count DESC
                LIMIT ?
                """,
                (date_limit, limit),
            )

            return [{"question": row[0], "count": row[1]} for row in cursor.fetchall()]

    def get_satisfaction_trend(self, days: int = 7) -> dict[str, Any]:
        """Obtiene tendencia de satisfacción en los últimos N días."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            # Satisfacción general
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END) as helpful
                FROM feedback
                WHERE timestamp >= ?
                """,
                (date_limit,),
            )
            total, helpful = cursor.fetchone()
            satisfaction_rate = (helpful / total * 100) if total > 0 else 0

            # Satisfacción por día
            cursor.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as total,
                    SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END) as helpful
                FROM feedback
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                """,
                (date_limit,),
            )

            daily_satisfaction = []
            for row in cursor.fetchall():
                date, total_day, helpful_day = row
                rate = (helpful_day / total_day * 100) if total_day > 0 else 0
                daily_satisfaction.append({
                    "date": date,
                    "total": total_day,
                    "helpful": helpful_day,
                    "satisfaction_rate": round(rate, 2),
                })

            return {
                "overall_satisfaction_rate": round(satisfaction_rate, 2),
                "total_feedback": total,
                "daily_satisfaction": daily_satisfaction,
                "period_days": days,
            }

    def get_top_topics(self, limit: int = 10, days: int = 7) -> list[dict[str, Any]]:
        """Obtiene los temas/procesos más consultados basado en references."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT qr.process, COUNT(*) as count
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE q.timestamp >= ? AND qr.process IS NOT NULL
                GROUP BY qr.process
                ORDER BY count DESC
                LIMIT ?
                """,
                (date_limit, limit),
            )

            return [{"topic": row[0], "count": row[1]} for row in cursor.fetchall()]

    def get_avg_response_time(self, days: int = 7) -> dict[str, Any]:
        """Obtiene tiempo promedio de respuesta."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT
                    AVG(response_time_ms) as avg_time,
                    MIN(response_time_ms) as min_time,
                    MAX(response_time_ms) as max_time,
                    COUNT(*) as total
                FROM queries
                WHERE timestamp >= ? AND response_time_ms IS NOT NULL
                """,
                (date_limit,),
            )

            avg_time, min_time, max_time, total = cursor.fetchone()

            return {
                "avg_response_time_ms": round(avg_time, 2) if avg_time else 0,
                "min_response_time_ms": round(min_time, 2) if min_time else 0,
                "max_response_time_ms": round(max_time, 2) if max_time else 0,
                "total_queries_with_timing": total,
                "period_days": days,
            }

    def get_coverage_stats(self, days: int = 7) -> dict[str, Any]:
        """Obtiene estadísticas de cobertura (queries respondidas vs fallidas)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN error IS NULL THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN num_references = 0 THEN 1 ELSE 0 END) as no_references
                FROM queries
                WHERE timestamp >= ?
                """,
                (date_limit,),
            )

            total, successful, failed, no_references = cursor.fetchone()

            coverage_rate = (successful / total * 100) if total > 0 else 0

            return {
                "total_queries": total,
                "successful_queries": successful,
                "failed_queries": failed,
                "queries_without_references": no_references,
                "coverage_rate": round(coverage_rate, 2),
                "period_days": days,
            }

    def get_dashboard_summary(self, days: int = 7) -> dict[str, Any]:
        """Obtiene un resumen completo para el dashboard."""
        return {
            "query_volume": self.get_query_volume_stats(days),
            "satisfaction": self.get_satisfaction_trend(days),
            "top_questions": self.get_top_questions(10, days),
            "top_topics": self.get_top_topics(10, days),
            "response_time": self.get_avg_response_time(days),
            "coverage": self.get_coverage_stats(days),
        }
