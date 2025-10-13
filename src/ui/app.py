from __future__ import annotations

import json
from typing import Any, Dict

import requests
import streamlit as st

from config.settings import get_settings

settings = get_settings()
API_BASE_URL = settings.api_base_url.rstrip("/")

st.set_page_config(page_title="Asistente Organizacional", layout="wide")
st.title("Asistente Organizacional")
st.caption("Consulta procedimientos, responsables e incidentes históricos.")


def ask_question(question: str, metadata_filters: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = {"question": question, "metadata_filters": metadata_filters}
    response = requests.post(f"{API_BASE_URL}/ask", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_feedback(question: str, answer: str, is_helpful: bool, comment: str | None) -> None:
    payload = {
        "question": question,
        "answer": answer,
        "is_helpful": is_helpful,
        "comment": comment or "",
    }
    response = requests.post(f"{API_BASE_URL}/feedback", json=payload, timeout=15)
    response.raise_for_status()


with st.form("query-form"):
    question = st.text_area(
        "Pregunta", placeholder="¿Cuál es el flujo para autorizar un reembolso de prestaciones médicas?"
    )
    col1, col2 = st.columns(2)
    with col1:
        process_filter = st.text_input("Filtrar por proceso (opcional)")
    with col2:
        responsible_filter = st.text_input("Filtrar por responsable (opcional)")
    submitted = st.form_submit_button("Consultar", type="primary")

if submitted and question.strip():
    filters = {}
    if process_filter:
        filters["process"] = process_filter
    if responsible_filter:
        filters["responsible"] = responsible_filter
    filters = filters or None

    try:
        result = ask_question(question, filters)
    except requests.HTTPError as exc:
        st.error(f"Error al consultar la API: {exc.response.text}")
    except requests.RequestException as exc:
        st.error(f"No fue posible contactar al servicio: {exc}")
    else:
        st.subheader("Respuesta")
        st.write(result["answer"])

        st.subheader("Referencias")
        for ref in result["references"]:
            st.markdown(f"- **Fuente:** {ref['source']} | Proceso: {ref.get('process', 'N/D')}")
            if ref.get("keywords"):
                st.caption(f"Palabras clave: {', '.join(ref['keywords'])}")

        with st.expander("Contexto utilizado"):
            st.text(result["raw_context"])

        st.divider()
        st.write("¿Te ayudó la respuesta?")
        col_left, col_right = st.columns(2)
        with col_left:
            if st.button("Sí, fue útil", key="feedback-yes"):
                try:
                    send_feedback(question, result["answer"], True, None)
                    st.success("¡Gracias por tu feedback!")
                except requests.RequestException:
                    st.warning("No se registró el feedback.")
        with col_right:
            comment = st.text_input("Si no, cuéntanos por qué", key="feedback-comment")
            if st.button("No, mejorar", key="feedback-no"):
                try:
                    send_feedback(question, result["answer"], False, comment or "")
                    st.success("Feedback registrado.")
                except requests.RequestException:
                    st.warning("No se registró el feedback.")
