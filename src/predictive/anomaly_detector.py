"""
Detector de anomalías y alertas automáticas.
Identifica patrones inusuales que requieren atención.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detecta anomalías en el uso del sistema:
    - Picos inusuales de consultas
    - Caída repentina en satisfacción
    - Temas con error rate alto
    - Cambios drásticos en patrones de uso
    """

    def __init__(self, analytics_db_path: Path):
        self.db_path = analytics_db_path

    def detect_query_spikes(
        self, threshold: float = 2.0, window_days: int = 7
    ) -> list[dict[str, Any]]:
        """
        Detecta picos inusuales en el volumen de consultas.

        Args:
            threshold: Factor de desviación (2.0 = el doble del promedio)
            window_days: Ventana de tiempo para calcular baseline

        Returns:
            Lista de picos detectados con detalles
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Calcular promedio histórico
            date_limit = (datetime.now() - timedelta(days=window_days)).isoformat()

            cursor.execute(
                """
                SELECT COUNT(*) as total_queries
                FROM queries
                WHERE timestamp >= ? AND timestamp < DATE('now')
                """,
                (date_limit,),
            )

            historical_total = cursor.fetchone()[0]
            daily_average = historical_total / window_days if window_days > 0 else 0

            # Consultas de hoy
            cursor.execute(
                """
                SELECT COUNT(*) as today_queries
                FROM queries
                WHERE DATE(timestamp) = DATE('now')
                """
            )

            today_count = cursor.fetchone()[0]

            anomalies = []

            if daily_average > 0 and today_count > daily_average * threshold:
                anomalies.append(
                    {
                        "type": "query_spike",
                        "date": datetime.now().date().isoformat(),
                        "current_volume": today_count,
                        "expected_volume": round(daily_average, 1),
                        "spike_factor": round(today_count / daily_average, 2),
                        "severity": "high" if today_count > daily_average * 3 else "medium",
                        "message": f"Pico de consultas detectado: {today_count} queries vs promedio de {daily_average:.1f}",
                    }
                )

            # Detectar picos por tema
            cursor.execute(
                """
                SELECT qr.process, COUNT(*) as today_count
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE DATE(q.timestamp) = DATE('now') AND qr.process IS NOT NULL
                GROUP BY qr.process
                """
            )

            topic_today = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT qr.process, COUNT(*) / ? as daily_avg
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE q.timestamp >= ? AND q.timestamp < DATE('now') AND qr.process IS NOT NULL
                GROUP BY qr.process
                """,
                (window_days, date_limit),
            )

            topic_avg = {row[0]: row[1] for row in cursor.fetchall()}

            for topic, today in topic_today.items():
                avg = topic_avg.get(topic, 0)
                if avg > 0 and today > avg * threshold:
                    anomalies.append(
                        {
                            "type": "topic_spike",
                            "topic": topic,
                            "date": datetime.now().date().isoformat(),
                            "current_volume": today,
                            "expected_volume": round(avg, 1),
                            "spike_factor": round(today / avg, 2),
                            "severity": "high" if today > avg * 3 else "medium",
                            "message": f"Pico de interés en '{topic}': {today} consultas vs promedio de {avg:.1f}",
                        }
                    )

            return anomalies

    def detect_satisfaction_drops(
        self, threshold: float = 0.7, window_days: int = 7
    ) -> list[dict[str, Any]]:
        """
        Detecta caídas significativas en satisfacción del usuario.

        Args:
            threshold: Umbral de satisfacción aceptable (0.7 = 70%)
            window_days: Ventana para comparar

        Returns:
            Lista de caídas detectadas
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Satisfacción histórica
            date_limit = (datetime.now() - timedelta(days=window_days)).isoformat()

            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END) as helpful
                FROM feedback
                WHERE timestamp >= ? AND timestamp < DATE('now')
                """,
                (date_limit,),
            )

            total_hist, helpful_hist = cursor.fetchone()
            historical_rate = (helpful_hist / total_hist) if total_hist > 0 else 1.0

            # Satisfacción de hoy
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END) as helpful
                FROM feedback
                WHERE DATE(timestamp) = DATE('now')
                """
            )

            total_today, helpful_today = cursor.fetchone()
            today_rate = (helpful_today / total_today) if total_today > 0 else 1.0

            anomalies = []

            if total_today >= 5 and today_rate < threshold and today_rate < historical_rate * 0.8:
                anomalies.append(
                    {
                        "type": "satisfaction_drop",
                        "date": datetime.now().date().isoformat(),
                        "current_rate": round(today_rate * 100, 1),
                        "historical_rate": round(historical_rate * 100, 1),
                        "drop_percentage": round((historical_rate - today_rate) * 100, 1),
                        "severity": "high",
                        "message": f"Caída en satisfacción: {today_rate*100:.1f}% hoy vs {historical_rate*100:.1f}% histórico",
                    }
                )

            return anomalies

    def detect_high_error_topics(
        self, error_threshold: float = 0.3, min_queries: int = 5
    ) -> list[dict[str, Any]]:
        """
        Identifica temas con alta tasa de errores.

        Args:
            error_threshold: Tasa de error mínima para alertar (0.3 = 30%)
            min_queries: Mínimo de consultas para considerar

        Returns:
            Lista de temas problemáticos
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    qr.process,
                    COUNT(*) as total_queries,
                    SUM(CASE WHEN q.error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM query_references qr
                JOIN queries q ON qr.query_id = q.id
                WHERE qr.process IS NOT NULL
                GROUP BY qr.process
                HAVING total_queries >= ?
                """,
                (min_queries,),
            )

            problem_topics = []
            for row in cursor.fetchall():
                topic, total, errors = row
                error_rate = errors / total if total > 0 else 0

                if error_rate >= error_threshold:
                    problem_topics.append(
                        {
                            "type": "high_error_rate",
                            "topic": topic,
                            "total_queries": total,
                            "error_count": errors,
                            "error_rate": round(error_rate * 100, 1),
                            "severity": "high" if error_rate > 0.5 else "medium",
                            "message": f"Alta tasa de errores en '{topic}': {error_rate*100:.1f}%",
                        }
                    )

            return problem_topics

    def detect_usage_pattern_changes(self, days: int = 14) -> list[dict[str, Any]]:
        """
        Detecta cambios significativos en patrones de uso (horarios, días de semana, etc.).

        Args:
            days: Período a analizar

        Returns:
            Lista de cambios detectados
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            date_limit = (datetime.now() - timedelta(days=days)).isoformat()
            midpoint = (datetime.now() - timedelta(days=days // 2)).isoformat()

            # Distribución horaria en primera mitad
            cursor.execute(
                """
                SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as count
                FROM queries
                WHERE timestamp >= ? AND timestamp < ?
                GROUP BY hour
                """,
                (date_limit, midpoint),
            )
            first_half_hours = {row[0]: row[1] for row in cursor.fetchall()}

            # Distribución horaria en segunda mitad
            cursor.execute(
                """
                SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as count
                FROM queries
                WHERE timestamp >= ?
                GROUP BY hour
                """,
                (midpoint,),
            )
            second_half_hours = {row[0]: row[1] for row in cursor.fetchall()}

            changes = []

            # Detectar cambios significativos en horarios pico
            for hour in range(24):
                old_count = first_half_hours.get(hour, 0)
                new_count = second_half_hours.get(hour, 0)

                if old_count > 0:
                    change_factor = new_count / old_count
                    if change_factor > 2 or change_factor < 0.5:
                        changes.append(
                            {
                                "type": "usage_pattern_change",
                                "hour": hour,
                                "old_average": round(old_count / (days // 2), 1),
                                "new_average": round(new_count / (days // 2), 1),
                                "change_factor": round(change_factor, 2),
                                "severity": "low",
                                "message": f"Cambio en patrón de uso a las {hour}:00 horas",
                            }
                        )

            return changes

    def get_all_alerts(self, days: int = 7) -> dict[str, Any]:
        """
        Obtiene todas las alertas y anomalías detectadas.

        Args:
            days: Ventana de tiempo para análisis

        Returns:
            Dict con todas las categorías de alertas
        """
        alerts = {
            "timestamp": datetime.now().isoformat(),
            "query_spikes": self.detect_query_spikes(window_days=days),
            "satisfaction_drops": self.detect_satisfaction_drops(window_days=days),
            "high_error_topics": self.detect_high_error_topics(),
            "usage_pattern_changes": self.detect_usage_pattern_changes(days=days),
        }

        # Calcular total de alertas
        total_alerts = sum(len(v) for v in alerts.values() if isinstance(v, list))
        alerts["total_alerts"] = total_alerts

        # Determinar severidad general
        high_severity_count = sum(
            1
            for v in alerts.values()
            if isinstance(v, list)
            for item in v
            if item.get("severity") == "high"
        )

        if high_severity_count > 0:
            alerts["overall_severity"] = "high"
        elif total_alerts > 0:
            alerts["overall_severity"] = "medium"
        else:
            alerts["overall_severity"] = "low"

        return alerts
