"""
Dashboard de administración para gestión de documentos y feedback.
"""
import sys
from pathlib import Path

import requests
import streamlit as st
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config.settings import get_settings
from src.ui.auth import AuthManager, require_auth, render_user_menu

settings = get_settings()
API_BASE_URL = settings.api_base_url


def format_bytes(bytes_value: int) -> str:
    """Formatea bytes a unidad legible."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


def format_datetime(iso_string: str) -> str:
    """Formatea datetime ISO a formato legible."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_string


def get_api_headers():
    """Obtener headers con autenticación para requests a la API."""
    return AuthManager.get_headers()


# --- Configuración de página ---
st.set_page_config(
    page_title="Panel de Administración",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Requerir autenticación
user = require_auth()

# Verificar que es admin
if user["role"] != "admin":
    st.error(f"❌ Acceso denegado. Se requieren permisos de administrador. Tu rol: {user['role']}")
    st.stop()

st.title("⚙️ Panel de Administración")
st.markdown("Gestión de documentos y feedback del asistente organizacional")

# Renderizar menú del usuario
render_user_menu()

# --- Sidebar con navegación ---
st.sidebar.title("Navegación")
page = st.sidebar.radio(
    "Selecciona una sección:",
    ["📁 Gestión de Documentos", "💬 Gestión de Feedback", "📊 Estadísticas"],
)

# --- Sección: Gestión de Documentos ---
if page == "📁 Gestión de Documentos":
    st.header("📁 Gestión de Documentos")

    # Tabs para organizar funcionalidades
    tab1, tab2, tab3 = st.tabs(["📋 Documentos", "⬆️ Subir Documento", "📊 Estadísticas"])

    # Tab 1: Lista de documentos
    with tab1:
        st.subheader("Documentos Indexados")

        if st.button("🔄 Actualizar Lista", key="refresh_docs"):
            st.rerun()

        try:
            response = requests.get(f"{API_BASE_URL}/admin/documents", headers=get_api_headers(), timeout=10)
            response.raise_for_status()
            data = response.json()

            if data["total"] == 0:
                st.info("No hay documentos indexados en el sistema.")
            else:
                st.success(f"**Total de documentos:** {data['total']}")

                # Mostrar tabla de documentos
                for doc in data["documents"]:
                    with st.expander(f"📄 {doc['filename']} ({format_bytes(doc['size_bytes'])})"):
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            st.write(f"**ID:** `{doc['id']}`")
                            st.write(f"**Tamaño:** {format_bytes(doc['size_bytes'])}")
                            st.write(f"**Subido:** {format_datetime(doc['uploaded_at'])}")
                            st.write(f"**Hash:** `{doc['file_hash'][:16]}...`")
                            st.write(f"**Estado:** {doc['status']}")

                        with col2:
                            if st.button("🗑️ Eliminar", key=f"delete_{doc['id']}"):
                                # Confirmar eliminación
                                if st.session_state.get(f"confirm_delete_{doc['id']}", False):
                                    try:
                                        del_response = requests.delete(
                                            f"{API_BASE_URL}/admin/documents/{doc['id']}",
                                            timeout=10,
                                        )
                                        del_response.raise_for_status()
                                        st.success(f"Documento '{doc['filename']}' eliminado")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")
                                else:
                                    st.session_state[f"confirm_delete_{doc['id']}"] = True
                                    st.warning("Haz clic de nuevo para confirmar")

        except requests.exceptions.RequestException as e:
            st.error(f"Error al conectar con la API: {e}")
            st.info("Asegúrate de que el servidor FastAPI esté corriendo en el puerto 8000")

    # Tab 2: Subir documento
    with tab2:
        st.subheader("⬆️ Subir Nuevo Documento")

        st.info(
            "**Formatos soportados:** .txt, .md, .pdf, .docx, .doc\n\n"
            "El documento será procesado y agregado al vector store automáticamente."
        )

        uploaded_file = st.file_uploader(
            "Selecciona un archivo",
            type=["txt", "md", "pdf", "docx", "doc"],
            help="Sube un documento para agregarlo al sistema de conocimiento",
        )

        if uploaded_file is not None:
            st.write(f"**Archivo seleccionado:** {uploaded_file.name}")
            st.write(f"**Tamaño:** {format_bytes(uploaded_file.size)}")

            if st.button("📤 Subir Documento", type="primary"):
                with st.spinner("Subiendo documento..."):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                        response = requests.post(
                            f"{API_BASE_URL}/admin/documents", files=files, timeout=30
                        )
                        response.raise_for_status()
                        result = response.json()

                        st.success(f"✅ Documento subido exitosamente!")
                        st.json(result)

                        # Trigger ingestion
                        st.info("Ejecutando ingesta automática...")
                        ingest_response = requests.post(
                            f"{API_BASE_URL}/admin/ingest", timeout=120
                        )
                        ingest_response.raise_for_status()
                        ingest_result = ingest_response.json()

                        st.success(
                            f"✅ Ingesta completada: {ingest_result['documents_processed']} "
                            f"documentos procesados en {ingest_result['time_taken_seconds']}s"
                        )

                        st.balloons()

                    except requests.exceptions.RequestException as e:
                        if hasattr(e, "response") and e.response is not None:
                            error_detail = e.response.json().get("detail", str(e))
                            st.error(f"❌ Error: {error_detail}")
                        else:
                            st.error(f"❌ Error al subir documento: {e}")

    # Tab 3: Estadísticas de documentos
    with tab3:
        st.subheader("📊 Estadísticas del Sistema")

        try:
            response = requests.get(f"{API_BASE_URL}/admin/documents/stats", headers=get_api_headers(), timeout=10)
            response.raise_for_status()
            stats = response.json()

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("📄 Total Documentos", stats["total_documents"])
                st.metric("🗑️ Documentos Eliminados", stats["deleted_documents"])

            with col2:
                st.metric("💾 Tamaño Total", f"{stats['total_size_mb']} MB")
                st.metric(
                    "📅 Última Actualización",
                    format_datetime(stats["last_updated"]) if stats["last_updated"] else "N/A",
                )

            with col3:
                st.metric(
                    "🔄 Última Ingesta",
                    format_datetime(stats["last_ingestion"]) if stats["last_ingestion"] else "N/A",
                )

            # Botón de re-ingesta manual
            st.divider()
            st.subheader("🔄 Re-ingesta Manual")
            st.warning(
                "**Advertencia:** Esto volverá a procesar todos los documentos activos "
                "y puede tomar varios minutos."
            )

            if st.button("🔄 Ejecutar Re-ingesta", type="secondary"):
                with st.spinner("Ejecutando re-ingesta... Esto puede tomar varios minutos."):
                    try:
                        response = requests.post(f"{API_BASE_URL}/admin/ingest", headers=get_api_headers(), timeout=300)
                        response.raise_for_status()
                        result = response.json()

                        if result["status"] == "completed":
                            st.success(
                                f"✅ Re-ingesta completada!\n\n"
                                f"- Documentos procesados: {result['documents_processed']}\n"
                                f"- Tiempo: {result['time_taken_seconds']}s"
                            )
                        elif result["status"] == "skipped":
                            st.info(result["message"])
                    except Exception as e:
                        st.error(f"❌ Error durante la ingesta: {e}")

        except requests.exceptions.RequestException as e:
            st.error(f"Error al obtener estadísticas: {e}")


# --- Sección: Gestión de Feedback ---
elif page == "💬 Gestión de Feedback":
    st.header("💬 Gestión de Feedback")

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        days = st.selectbox("Período", [7, 15, 30, 60, 90], index=2, key="feedback_days")
    with col2:
        category_filter = st.selectbox(
            "Categoría",
            ["Todas", "missing_info", "incorrect_answer", "unclear", "other"],
            key="category_filter",
        )
    with col3:
        status_filter = st.selectbox(
            "Estado", ["Todos", "pending", "reviewed", "actioned"], key="status_filter"
        )

    # Construir parámetros de query
    params = {"days": days}
    if category_filter != "Todas":
        params["category"] = category_filter
    if status_filter != "Todos":
        params["status"] = status_filter

    try:
        response = requests.get(
            f"{API_BASE_URL}/admin/feedback/negative", params=params, timeout=10
        )
        response.raise_for_status()
        data = response.json()

        st.info(f"**Total de feedback negativo:** {data['total']}")

        if data["total"] == 0:
            st.success("🎉 No hay feedback negativo pendiente para este filtro!")
        else:
            # Mostrar cada feedback
            for fb in data["feedback"]:
                with st.expander(
                    f"🔴 {fb['question'][:80]}... - {format_datetime(fb['timestamp'])}"
                ):
                    st.write(f"**Pregunta:** {fb['question']}")
                    st.write(f"**Comentario:** {fb['comment'] or 'Sin comentario'}")
                    st.write(f"**Categoría:** {fb['category'] or 'Sin categorizar'}")
                    st.write(f"**Estado:** {fb['status']}")
                    if fb["action_notes"]:
                        st.write(f"**Acción tomada:** {fb['action_notes']}")

                    st.divider()

                    # Acciones
                    col1, col2 = st.columns(2)

                    with col1:
                        if fb["status"] == "pending":
                            st.write("**Categorizar:**")
                            new_category = st.selectbox(
                                "Categoría",
                                ["missing_info", "incorrect_answer", "unclear", "other"],
                                key=f"cat_{fb['id']}",
                            )
                            if st.button("✅ Categorizar", key=f"categorize_{fb['id']}"):
                                try:
                                    cat_response = requests.put(
                                        f"{API_BASE_URL}/admin/feedback/{fb['id']}/categorize",
                                        json={"category": new_category},
                                        timeout=10,
                                    )
                                    cat_response.raise_for_status()
                                    st.success("Feedback categorizado")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")

                    with col2:
                        if fb["status"] in ["pending", "reviewed"]:
                            st.write("**Marcar como accionado:**")
                            action_notes = st.text_area(
                                "Notas de acción", key=f"notes_{fb['id']}", height=100
                            )
                            if st.button("✅ Marcar Accionado", key=f"action_{fb['id']}"):
                                if len(action_notes.strip()) >= 5:
                                    try:
                                        action_response = requests.put(
                                            f"{API_BASE_URL}/admin/feedback/{fb['id']}/action",
                                            json={"action_notes": action_notes},
                                            timeout=10,
                                        )
                                        action_response.raise_for_status()
                                        st.success("Feedback marcado como accionado")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                                else:
                                    st.warning("Las notas deben tener al menos 5 caracteres")

    except requests.exceptions.RequestException as e:
        st.error(f"Error al obtener feedback: {e}")


# --- Sección: Estadísticas ---
elif page == "📊 Estadísticas":
    st.header("📊 Estadísticas Generales")

    days = st.selectbox("Período de análisis", [7, 15, 30, 60, 90], index=2, key="stats_days")

    try:
        # Estadísticas de feedback
        response = requests.get(
            f"{API_BASE_URL}/admin/feedback/stats", params={"days": days}, timeout=10
        )
        response.raise_for_status()
        fb_stats = response.json()

        st.subheader("💬 Feedback")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Feedback", fb_stats["total_feedback"])
        with col2:
            st.metric("Positivo", fb_stats["positive_feedback"], delta="👍")
        with col3:
            st.metric("Negativo", fb_stats["negative_feedback"], delta="👎")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pendiente Revisión", fb_stats["pending_review"])
        with col2:
            st.metric("Accionado", fb_stats["actioned"])
        with col3:
            satisfaction = (
                (fb_stats["positive_feedback"] / fb_stats["total_feedback"] * 100)
                if fb_stats["total_feedback"] > 0
                else 0
            )
            st.metric("Tasa Satisfacción", f"{satisfaction:.1f}%")

        # Top issues
        st.divider()
        st.subheader("🔥 Top Temas con Problemas")

        if fb_stats["top_issues"]:
            for issue in fb_stats["top_issues"][:10]:
                st.write(
                    f"- **{issue['topic']}**: {issue['negative_count']} feedbacks negativos "
                    f"({issue['affected_queries']} queries afectadas)"
                )
        else:
            st.info("No hay temas con feedback negativo reciente")

        # Estadísticas por categoría
        st.divider()
        st.subheader("📋 Feedback por Categoría")
        if fb_stats["by_category"]:
            import pandas as pd
            import plotly.express as px

            df_cat = pd.DataFrame(
                list(fb_stats["by_category"].items()), columns=["Categoría", "Count"]
            )
            fig = px.pie(df_cat, values="Count", names="Categoría", title="Distribución por Categoría")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay feedback categorizado aún")

    except requests.exceptions.RequestException as e:
        st.error(f"Error al obtener estadísticas: {e}")

# --- Footer ---
st.sidebar.divider()
st.sidebar.info(
    "**Panel de Administración v1.0**\n\n"
    "Gestiona documentos, revisa feedback y monitorea el sistema."
)
