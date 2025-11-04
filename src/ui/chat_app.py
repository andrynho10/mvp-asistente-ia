"""
Interfaz de chat con memoria conversacional para el Asistente Organizacional.
Permite conversaciones multi-turno con contexto mantenido.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import requests
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config.settings import get_settings

settings = get_settings()
API_BASE_URL = settings.api_base_url.rstrip("/")


st.set_page_config(page_title="Chat - Asistente Organizacional", page_icon="💬", layout="wide")


def create_session() -> str:
    """Crea una nueva sesión conversacional."""
    response = requests.post(f"{API_BASE_URL}/sessions", params={"max_history": 5}, timeout=10)
    response.raise_for_status()
    return response.json()["session_id"]


def ask_question(
    question: str, session_id: str | None = None, metadata_filters: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Envía una pregunta con contexto de sesión."""
    payload = {"question": question, "session_id": session_id, "metadata_filters": metadata_filters}
    response = requests.post(f"{API_BASE_URL}/ask", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def send_feedback(question: str, answer: str, is_helpful: bool, comment: str | None) -> None:
    """Envía feedback sobre una respuesta."""
    payload = {
        "question": question,
        "answer": answer,
        "is_helpful": is_helpful,
        "comment": comment or "",
    }
    response = requests.post(f"{API_BASE_URL}/feedback", json=payload, timeout=15)
    response.raise_for_status()


def delete_session(session_id: str) -> None:
    """Elimina una sesión."""
    response = requests.delete(f"{API_BASE_URL}/sessions/{session_id}", timeout=10)
    response.raise_for_status()


# ===== Inicialización de estado =====
if "session_id" not in st.session_state:
    try:
        st.session_state.session_id = create_session()
        st.session_state.messages = []
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []


# ===== Header =====
col1, col2, col3 = st.columns([3, 1, 1])

with col1:
    st.title("💬 Chat - Asistente Organizacional")

with col2:
    if st.button("🗑️ Limpiar Chat", use_container_width=True):
        try:
            # Eliminar sesión antigua y crear nueva
            delete_session(st.session_state.session_id)
            st.session_state.session_id = create_session()
            st.session_state.messages = []
            st.rerun()
        except Exception as e:
            st.error(f"Error al limpiar chat: {e}")

with col3:
    st.caption(f"Sesión: {st.session_state.session_id[:8]}...")

st.caption(
    "Pregunta sobre procedimientos, políticas y procesos. "
    "El asistente recordará el contexto de la conversación."
)

st.divider()

# ===== Historial de mensajes =====
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]

        if role == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(content)
        elif role == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(content)

                # Mostrar referencias si existen
                if "references" in message and message["references"]:
                    with st.expander("📚 Ver referencias"):
                        for ref in message["references"]:
                            st.markdown(
                                f"- **Fuente:** `{ref['source']}` | Proceso: {ref.get('process', 'N/D')}"
                            )
                            if ref.get("keywords"):
                                st.caption(f"*Keywords:* {', '.join(ref['keywords'][:5])}")


# ===== Barra lateral con filtros =====
with st.sidebar:
    st.header("⚙️ Configuración")

    with st.expander("Filtros de búsqueda", expanded=False):
        process_filter = st.text_input("Filtrar por proceso")
        responsible_filter = st.text_input("Filtrar por responsable")

    st.divider()

    st.subheader("💡 Ejemplos de preguntas")
    st.markdown("""
    **Primera pregunta:**
    - "¿Cuál es el proceso de solicitud de vacaciones?"

    **Preguntas de seguimiento:**
    - "¿Y si necesito más de 15 días?"
    - "¿Quién debe aprobar la solicitud?"
    - "Dame más detalles sobre los plazos"
    """)

    st.divider()

    st.subheader("📊 Estadísticas")
    st.metric("Mensajes en esta sesión", len(st.session_state.messages))

    # Número de intercambios
    num_exchanges = len([m for m in st.session_state.messages if m["role"] == "user"])
    st.metric("Preguntas realizadas", num_exchanges)


# ===== Input de usuario =====
prompt = st.chat_input("Escribe tu pregunta aquí...")

if prompt:
    # Agregar mensaje del usuario al historial
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Mostrar mensaje del usuario inmediatamente
    with chat_container:
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

    # Preparar filtros
    filters = {}
    if process_filter:
        filters["process"] = process_filter
    if responsible_filter:
        filters["responsible"] = responsible_filter
    filters = filters or None

    # Obtener respuesta
    with st.spinner("🤔 Pensando..."):
        try:
            result = ask_question(prompt, st.session_state.session_id, filters)

            # Agregar respuesta al historial
            assistant_message = {
                "role": "assistant",
                "content": result["answer"],
                "references": result.get("references", []),
            }
            st.session_state.messages.append(assistant_message)

            # Mostrar respuesta
            with chat_container:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(result["answer"])

                    # Mostrar referencias
                    if result.get("references"):
                        with st.expander("📚 Ver referencias"):
                            for ref in result["references"]:
                                st.markdown(
                                    f"- **Fuente:** `{ref['source']}` | Proceso: {ref.get('process', 'N/D')}"
                                )
                                if ref.get("keywords"):
                                    st.caption(f"*Keywords:* {', '.join(ref['keywords'][:5])}")

            # Rerun para actualizar la UI
            st.rerun()

        except requests.HTTPError as exc:
            st.error(f"❌ Error al consultar la API: {exc.response.text if exc.response else exc}")
        except requests.RequestException as exc:
            st.error(f"❌ No fue posible contactar al servicio: {exc}")
        except Exception as exc:
            st.error(f"❌ Error inesperado: {exc}")


# ===== Feedback (solo para el último mensaje) =====
if len(st.session_state.messages) >= 2:
    last_user_msg = None
    last_assistant_msg = None

    # Encontrar el último intercambio
    for i in range(len(st.session_state.messages) - 1, -1, -1):
        if st.session_state.messages[i]["role"] == "assistant" and last_assistant_msg is None:
            last_assistant_msg = st.session_state.messages[i]
        elif st.session_state.messages[i]["role"] == "user" and last_user_msg is None:
            last_user_msg = st.session_state.messages[i]

        if last_user_msg and last_assistant_msg:
            break

    if last_user_msg and last_assistant_msg and "feedback_sent" not in last_assistant_msg:
        st.divider()
        st.write("¿Te ayudó la última respuesta?")

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button("👍 Sí, fue útil", key="feedback-yes", use_container_width=True):
                try:
                    send_feedback(
                        last_user_msg["content"], last_assistant_msg["content"], True, None
                    )
                    st.success("¡Gracias por tu feedback!")
                    last_assistant_msg["feedback_sent"] = True
                except Exception as e:
                    st.warning(f"No se pudo registrar el feedback: {e}")

        with col2:
            if st.button("👎 No, mejorar", key="feedback-no", use_container_width=True):
                st.session_state.show_comment = True

        if st.session_state.get("show_comment", False):
            with col3:
                comment = st.text_input("¿Qué podemos mejorar?", key="feedback-comment")
                if st.button("Enviar comentario", key="send-comment"):
                    try:
                        send_feedback(
                            last_user_msg["content"],
                            last_assistant_msg["content"],
                            False,
                            comment,
                        )
                        st.success("Feedback registrado. ¡Gracias!")
                        last_assistant_msg["feedback_sent"] = True
                        st.session_state.show_comment = False
                    except Exception as e:
                        st.warning(f"No se pudo registrar el feedback: {e}")


# ===== Footer =====
st.divider()
st.caption(
    "💡 **Tip:** Este asistente recuerda el contexto de tu conversación. "
    "Puedes hacer preguntas de seguimiento como '¿Y si...?' o 'Dame más detalles sobre eso'."
)
