"""Módulo de autenticación para interfaces Streamlit."""

import logging
from typing import Optional

import requests
import streamlit as st
from requests.exceptions import RequestException

from config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
API_BASE_URL = settings.api_base_url.rstrip("/")


class AuthManager:
    """Gestor de autenticación para Streamlit."""

    SESSION_TOKEN_KEY = "auth_token"
    SESSION_USER_KEY = "auth_user"
    SESSION_LOGIN_ATTEMPTED = "login_attempted"

    @staticmethod
    def is_authenticated() -> bool:
        """Verificar si el usuario está autenticado."""
        return SESSION_TOKEN_KEY in st.session_state

    @staticmethod
    def get_current_user() -> Optional[dict]:
        """Obtener el usuario actual del session state."""
        return st.session_state.get(SESSION_USER_KEY)

    @staticmethod
    def get_token() -> Optional[str]:
        """Obtener el token JWT del session state."""
        return st.session_state.get(SESSION_TOKEN_KEY)

    @staticmethod
    def login(username: str, password: str) -> bool:
        """
        Intentar login con credenciales.

        Args:
            username: Nombre de usuario o email
            password: Contraseña

        Returns:
            True si el login fue exitoso
        """
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            st.session_state[SESSION_TOKEN_KEY] = data["access_token"]
            st.session_state[SESSION_USER_KEY] = data["user"]

            logger.info(f"Login exitoso para usuario {username}")
            return True

        except RequestException as e:
            logger.warning(f"Error en login: {e}")
            return False

    @staticmethod
    def register(username: str, email: str, password: str, full_name: Optional[str] = None) -> bool:
        """
        Registrar un nuevo usuario.

        Args:
            username: Nombre de usuario
            email: Email
            password: Contraseña
            full_name: Nombre completo (opcional)

        Returns:
            True si el registro fue exitoso
        """
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password,
                    "full_name": full_name,
                },
                timeout=10,
            )
            response.raise_for_status()

            logger.info(f"Registro exitoso para usuario {username}")
            return True

        except RequestException as e:
            logger.warning(f"Error en registro: {e}")
            return False

    @staticmethod
    def logout() -> None:
        """Logout del usuario actual."""
        username = st.session_state.get(SESSION_USER_KEY, {}).get("username", "usuario")
        st.session_state.pop(SESSION_TOKEN_KEY, None)
        st.session_state.pop(SESSION_USER_KEY, None)
        logger.info(f"Logout para usuario {username}")

    @staticmethod
    def get_headers() -> dict:
        """
        Obtener headers con autenticación para requests.

        Returns:
            Dict con headers incluido Authorization si está autenticado
        """
        headers = {"Content-Type": "application/json"}

        token = AuthManager.get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers


def render_login_page() -> None:
    """Renderizar la página de login/registro."""
    st.set_page_config(page_title="Login - Asistente Organizacional", layout="centered")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.title("Asistente Organizacional")
        st.markdown("---")

        # Tabs para login y registro
        tab1, tab2 = st.tabs(["Iniciar sesión", "Crear cuenta"])

        with tab1:
            st.subheader("Iniciar sesión")

            with st.form("login-form"):
                username = st.text_input(
                    "Usuario o Email",
                    placeholder="tu@email.com o nombre_usuario",
                )
                password = st.text_input("Contraseña", type="password")
                submit = st.form_submit_button("Iniciar sesión", type="primary", use_container_width=True)

            if submit:
                if not username or not password:
                    st.error("Por favor completa todos los campos")
                elif AuthManager.login(username, password):
                    st.success("¡Bienvenido! Redirigiendo...")
                    st.rerun()
                else:
                    st.error("Credenciales inválidas. Intenta de nuevo.")

        with tab2:
            st.subheader("Crear cuenta")

            with st.form("register-form"):
                new_username = st.text_input("Nombre de usuario", placeholder="nombre_usuario")
                new_email = st.text_input("Email", placeholder="tu@email.com")
                new_full_name = st.text_input("Nombre completo (opcional)", placeholder="Tu Nombre")
                new_password = st.text_input("Contraseña (mín. 8 caracteres)", type="password")
                new_password_confirm = st.text_input("Confirmar contraseña", type="password")
                submit = st.form_submit_button("Crear cuenta", type="primary", use_container_width=True)

            if submit:
                if not new_username or not new_email or not new_password:
                    st.error("Por favor completa los campos obligatorios")
                elif len(new_password) < 8:
                    st.error("La contraseña debe tener al menos 8 caracteres")
                elif new_password != new_password_confirm:
                    st.error("Las contraseñas no coinciden")
                elif AuthManager.register(
                    new_username, new_email, new_password, new_full_name or None
                ):
                    st.success("¡Cuenta creada! Ahora inicia sesión con tus credenciales.")
                else:
                    st.error("No se pudo crear la cuenta. El usuario o email ya existe.")


def require_auth() -> dict:
    """
    Decorator para requerir autenticación en una página.

    Returns:
        Dict con información del usuario actual
    """
    if not AuthManager.is_authenticated():
        render_login_page()
        st.stop()

    return AuthManager.get_current_user()


def render_user_menu() -> None:
    """Renderizar el menú del usuario autenticado en la barra lateral."""
    user = AuthManager.get_current_user()

    if user:
        with st.sidebar:
            st.divider()
            st.markdown(f"**{user['full_name'] or user['username']}**")
            st.caption(f"Rol: {user['role']}")

            if st.button("Cerrar sesión", key="logout-btn"):
                AuthManager.logout()
                st.rerun()
