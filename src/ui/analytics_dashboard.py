"""
Dashboard de Analytics para el Asistente Organizacional.
Visualiza métricas clave de uso, satisfacción e impacto.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from config.settings import get_settings
from src.analytics import AnalyticsTracker, MetricsCalculator


def main():
    st.set_page_config(
        page_title="Analytics - Asistente Organizacional",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 Dashboard de Analytics")
    st.markdown("Métricas de uso, satisfacción e impacto del Asistente Organizacional")

    settings = get_settings()
    tracker = AnalyticsTracker(settings.analytics_db_path)
    calculator = MetricsCalculator(settings.analytics_db_path)

    # Selector de período
    st.sidebar.header("Configuración")
    days = st.sidebar.selectbox(
        "Período de análisis",
        options=[7, 14, 30, 60, 90],
        index=1,
        format_func=lambda x: f"Últimos {x} días",
    )

    # Obtener datos
    try:
        summary = calculator.get_dashboard_summary(days)
    except Exception as e:
        st.error(f"Error al cargar métricas: {e}")
        st.info("Asegúrate de que el sistema esté en uso y haya datos disponibles.")
        return

    # ===== KPIs Principales =====
    st.header("🎯 KPIs Principales")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_queries = summary["query_volume"]["total_queries"]
        st.metric(
            label="Total de Consultas",
            value=total_queries,
            delta=f"{summary['query_volume']['avg_queries_per_day']:.1f}/día",
        )

    with col2:
        satisfaction_rate = summary["satisfaction"]["overall_satisfaction_rate"]
        st.metric(
            label="Tasa de Satisfacción",
            value=f"{satisfaction_rate:.1f}%",
            delta="↑" if satisfaction_rate >= 70 else "↓",
        )

    with col3:
        coverage_rate = summary["coverage"]["coverage_rate"]
        st.metric(
            label="Cobertura de Conocimiento",
            value=f"{coverage_rate:.1f}%",
            delta="↑" if coverage_rate >= 80 else "↓",
        )

    with col4:
        avg_time = summary["response_time"]["avg_response_time_ms"]
        st.metric(
            label="Tiempo Promedio de Respuesta",
            value=f"{avg_time:.0f}ms",
            delta=f"max: {summary['response_time']['max_response_time_ms']:.0f}ms",
        )

    st.divider()

    # ===== Volumen de Consultas =====
    st.header("📈 Volumen de Consultas")

    queries_per_day = summary["query_volume"]["queries_per_day"]
    if queries_per_day:
        df_queries = {
            "Fecha": [q["date"] for q in queries_per_day],
            "Consultas": [q["count"] for q in queries_per_day],
        }

        fig_volume = px.line(
            df_queries,
            x="Fecha",
            y="Consultas",
            title=f"Consultas por día (últimos {days} días)",
            markers=True,
        )
        fig_volume.update_layout(hovermode="x unified")
        st.plotly_chart(fig_volume, use_container_width=True)
    else:
        st.info("No hay datos de consultas en el período seleccionado.")

    st.divider()

    # ===== Satisfacción del Usuario =====
    st.header("😊 Satisfacción del Usuario")

    col1, col2 = st.columns(2)

    with col1:
        total_feedback = summary["satisfaction"]["total_feedback"]
        if total_feedback > 0:
            daily_satisfaction = summary["satisfaction"]["daily_satisfaction"]

            df_satisfaction = {
                "Fecha": [s["date"] for s in daily_satisfaction],
                "Satisfacción (%)": [s["satisfaction_rate"] for s in daily_satisfaction],
            }

            fig_satisfaction = px.line(
                df_satisfaction,
                x="Fecha",
                y="Satisfacción (%)",
                title="Tendencia de Satisfacción",
                markers=True,
            )
            fig_satisfaction.add_hline(
                y=70,
                line_dash="dash",
                line_color="green",
                annotation_text="Objetivo: 70%",
            )
            fig_satisfaction.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig_satisfaction, use_container_width=True)
        else:
            st.info("No hay datos de feedback en el período seleccionado.")

    with col2:
        if total_feedback > 0:
            # Gauge de satisfacción
            fig_gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number+delta",
                    value=satisfaction_rate,
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": "Satisfacción General"},
                    delta={"reference": 70, "valueformat": ".1f"},
                    gauge={
                        "axis": {"range": [None, 100]},
                        "bar": {"color": "darkblue"},
                        "steps": [
                            {"range": [0, 50], "color": "lightgray"},
                            {"range": [50, 70], "color": "lightyellow"},
                            {"range": [70, 100], "color": "lightgreen"},
                        ],
                        "threshold": {
                            "line": {"color": "red", "width": 4},
                            "thickness": 0.75,
                            "value": 90,
                        },
                    },
                )
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

    st.divider()

    # ===== Top Consultas y Temas =====
    st.header("🔍 Análisis de Contenido")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 10 Preguntas Frecuentes")
        top_questions = summary["top_questions"]
        if top_questions:
            for i, q in enumerate(top_questions[:10], 1):
                st.write(f"**{i}.** {q['question'][:80]}... ({q['count']} veces)")
        else:
            st.info("No hay datos de preguntas en el período seleccionado.")

    with col2:
        st.subheader("Top Temas/Procesos Consultados")
        top_topics = summary["top_topics"]
        if top_topics:
            df_topics = {
                "Tema": [t["topic"] for t in top_topics],
                "Consultas": [t["count"] for t in top_topics],
            }

            fig_topics = px.bar(
                df_topics,
                x="Consultas",
                y="Tema",
                orientation="h",
                title="Temas más consultados",
            )
            st.plotly_chart(fig_topics, use_container_width=True)
        else:
            st.info("No hay datos de temas en el período seleccionado.")

    st.divider()

    # ===== Cobertura y Errores =====
    st.header("✅ Cobertura de Conocimiento")

    coverage = summary["coverage"]
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Consultas Exitosas", coverage["successful_queries"])

    with col2:
        st.metric("Consultas Fallidas", coverage["failed_queries"])

    with col3:
        st.metric("Sin Referencias", coverage["queries_without_references"])

    # Gráfico de cobertura
    if coverage["total_queries"] > 0:
        fig_coverage = go.Figure(
            data=[
                go.Pie(
                    labels=["Exitosas", "Fallidas", "Sin Referencias"],
                    values=[
                        coverage["successful_queries"],
                        coverage["failed_queries"],
                        coverage["queries_without_references"],
                    ],
                    hole=0.3,
                )
            ]
        )
        fig_coverage.update_layout(title_text="Distribución de Consultas")
        st.plotly_chart(fig_coverage, use_container_width=True)

    st.divider()

    # ===== Indicadores de Impacto =====
    st.header("🎯 Indicadores de Impacto Organizacional")

    st.markdown("""
    Estos indicadores demuestran el valor del asistente para la organización:
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📉 Reducción de Carga de Trabajo")
        successful_queries = coverage.get("successful_queries", 0) or 0

        if successful_queries > 0:
            # Baseline: tiempo promedio por consulta manual (ajustable)
            BASELINE_MINUTES = 5  # ← CAMBIAR ESTE VALOR según investigación empírica
            time_saved_minutes = successful_queries * BASELINE_MINUTES
            time_saved_hours = time_saved_minutes / 60

            st.metric(
                "Tiempo Ahorrado (estimado)",
                f"{time_saved_hours:.1f} horas",
                delta=f"{successful_queries} consultas resueltas",
            )

            st.info(
                f"**Cálculo:** {successful_queries} consultas × {BASELINE_MINUTES} min/consulta = {time_saved_minutes:.0f} minutos"
            )
        else:
            st.info("No hay datos suficientes para calcular el tiempo ahorrado. Usa el sistema para generar métricas.")

    with col2:
        st.subheader("⚡ Eficiencia del Sistema")

        if avg_time and avg_time > 0:
            avg_response = avg_time / 1000  # convertir a segundos
            BASELINE_MINUTES = 5  # ← CAMBIAR ESTE VALOR (debe coincidir con col1)
            baseline_seconds = BASELINE_MINUTES * 60

            st.metric(
                "Velocidad de Respuesta",
                f"{avg_response:.2f} seg",
                delta=f"vs ~{BASELINE_MINUTES} min (consulta humana)",
            )

            efficiency_factor = baseline_seconds / avg_response
            st.info(f"**{efficiency_factor:.1f}x más rápido** que consulta humana tradicional")
        else:
            st.info("No hay datos de tiempo de respuesta. Realiza consultas para generar métricas.")

    st.divider()

    # ===== Recomendaciones =====
    st.header("💡 Recomendaciones")

    recommendations = []

    # Validar que tenemos datos suficientes
    total_queries_count = coverage.get("total_queries", 0) or 0

    if total_queries_count == 0:
        st.info("📊 **No hay datos suficientes para generar recomendaciones.** Usa el sistema para generar métricas de uso.")
    else:
        if satisfaction_rate and satisfaction_rate < 70:
            recommendations.append(
                "⚠️ **Satisfacción baja**: Revisar respuestas con feedback negativo y mejorar la base de conocimiento."
            )

        if coverage_rate and coverage_rate < 80:
            recommendations.append(
                "⚠️ **Cobertura insuficiente**: Ampliar documentación en áreas con muchas consultas sin respuesta."
            )

        queries_without_refs = coverage.get("queries_without_references", 0) or 0
        if queries_without_refs > total_queries_count * 0.1:
            recommendations.append(
                "⚠️ **Muchas consultas sin referencias**: Considerar agregar más documentos a la base de conocimiento."
            )

        if avg_time and avg_time > 5000:  # más de 5 segundos
            recommendations.append(
                "⚠️ **Tiempo de respuesta alto**: Considerar optimizar el vector store o reducir top_k."
            )

        if len(top_questions) > 0 and top_questions[0]["count"] > 10:
            recommendations.append(
                f"💡 **Pregunta muy frecuente**: '{top_questions[0]['question'][:50]}...' - Considerar crear contenido específico."
            )

        if not recommendations:
            st.success("✅ **Sistema operando de manera óptima**. Todas las métricas están en rangos aceptables.")
        else:
            for rec in recommendations:
                st.warning(rec)

    # Footer
    st.divider()
    st.caption(f"Dashboard actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption(f"Base de datos: {settings.analytics_db_path}")


if __name__ == "__main__":
    main()
