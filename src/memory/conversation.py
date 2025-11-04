"""
Sistema de memoria conversacional para el asistente.
Mantiene el contexto de conversaciones entre múltiples turnos.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import logging

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Gestiona la memoria conversacional de una sesión específica.
    Almacena historial de mensajes y contexto.
    """

    def __init__(self, session_id: str, max_history: int = 5):
        """
        Args:
            session_id: Identificador único de la sesión
            max_history: Número máximo de intercambios a recordar (default: 5)
        """
        self.session_id = session_id
        self.max_history = max_history
        self.messages: list[dict[str, str]] = []

    def add_user_message(self, content: str) -> None:
        """Agrega un mensaje del usuario al historial."""
        self.messages.append({"role": "user", "content": content})
        self._trim_history()

    def add_assistant_message(self, content: str) -> None:
        """Agrega un mensaje del asistente al historial."""
        self.messages.append({"role": "assistant", "content": content})
        self._trim_history()

    def add_exchange(self, user_message: str, assistant_message: str) -> None:
        """Agrega un intercambio completo (pregunta + respuesta)."""
        self.add_user_message(user_message)
        self.add_assistant_message(assistant_message)

    def get_history(self) -> list[dict[str, str]]:
        """Obtiene el historial completo de mensajes."""
        return self.messages.copy()

    def get_context_string(self) -> str:
        """
        Genera un string formateado del historial para incluir en el prompt.

        Returns:
            String con el historial formateado, o vacío si no hay historial.
        """
        if not self.messages:
            return ""

        context_parts = ["Historial de conversación:"]
        for msg in self.messages:
            role = "Usuario" if msg["role"] == "user" else "Asistente"
            context_parts.append(f"{role}: {msg['content']}")

        return "\n".join(context_parts)

    def _trim_history(self) -> None:
        """Mantiene solo los últimos N intercambios (2 mensajes = 1 intercambio)."""
        max_messages = self.max_history * 2  # user + assistant por intercambio
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]

    def clear(self) -> None:
        """Limpia todo el historial."""
        self.messages.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serializa la memoria a diccionario."""
        return {
            "session_id": self.session_id,
            "max_history": self.max_history,
            "messages": self.messages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationMemory:
        """Deserializa memoria desde diccionario."""
        memory = cls(session_id=data["session_id"], max_history=data.get("max_history", 5))
        memory.messages = data.get("messages", [])
        return memory


class SessionManager:
    """
    Gestiona sesiones de conversación y persiste en SQLite.
    Permite recuperar sesiones activas y limpiar sesiones antiguas.
    """

    def __init__(self, db_path: Path, session_timeout_hours: int = 24):
        """
        Args:
            db_path: Path a la base de datos SQLite
            session_timeout_hours: Horas antes de considerar una sesión expirada
        """
        self.db_path = db_path
        self.session_timeout_hours = session_timeout_hours
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Cache en memoria de sesiones activas
        self._cache: dict[str, ConversationMemory] = {}

    def _init_db(self) -> None:
        """Inicializa la tabla de sesiones."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at DATETIME NOT NULL,
                    last_activity DATETIME NOT NULL,
                    memory_data TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity)"
            )

            conn.commit()
            logger.info(f"Base de datos de sesiones inicializada en {self.db_path}")

    def create_session(self, max_history: int = 5) -> str:
        """
        Crea una nueva sesión.

        Args:
            max_history: Número de intercambios a recordar

        Returns:
            session_id: ID único de la sesión creada
        """
        session_id = str(uuid.uuid4())
        memory = ConversationMemory(session_id=session_id, max_history=max_history)

        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (session_id, created_at, last_activity, memory_data, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, now, now, json.dumps(memory.to_dict()), None),
            )
            conn.commit()

        self._cache[session_id] = memory
        logger.info(f"Sesión creada: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[ConversationMemory]:
        """
        Obtiene una sesión existente.

        Args:
            session_id: ID de la sesión

        Returns:
            ConversationMemory o None si no existe o expiró
        """
        # Buscar en cache
        if session_id in self._cache:
            return self._cache[session_id]

        # Buscar en DB
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT memory_data, last_activity
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,),
            )

            row = cursor.fetchone()

            if not row:
                return None

            # Verificar si expiró
            last_activity = datetime.fromisoformat(row["last_activity"])
            timeout_delta = timedelta(hours=self.session_timeout_hours)

            if datetime.now() - last_activity > timeout_delta:
                logger.info(f"Sesión {session_id} expirada")
                self.delete_session(session_id)
                return None

            # Cargar memoria
            memory_data = json.loads(row["memory_data"])
            memory = ConversationMemory.from_dict(memory_data)

            # Cachear
            self._cache[session_id] = memory
            return memory

    def save_session(self, memory: ConversationMemory) -> None:
        """Persiste una sesión en la base de datos."""
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET last_activity = ?, memory_data = ?
                WHERE session_id = ?
                """,
                (now, json.dumps(memory.to_dict()), memory.session_id),
            )
            conn.commit()

        # Actualizar cache
        self._cache[memory.session_id] = memory

    def delete_session(self, session_id: str) -> None:
        """Elimina una sesión."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()

        # Remover de cache
        self._cache.pop(session_id, None)
        logger.info(f"Sesión eliminada: {session_id}")

    def cleanup_expired_sessions(self) -> int:
        """
        Elimina sesiones expiradas.

        Returns:
            Número de sesiones eliminadas
        """
        timeout_delta = timedelta(hours=self.session_timeout_hours)
        cutoff_time = (datetime.now() - timeout_delta).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM sessions
                WHERE last_activity < ?
                """,
                (cutoff_time,),
            )
            deleted_count = cursor.rowcount
            conn.commit()

        # Limpiar cache
        expired_ids = [
            sid
            for sid, mem in self._cache.items()
            if datetime.now()
            - datetime.fromisoformat(
                self._get_last_activity(sid) or datetime.now().isoformat()
            )
            > timeout_delta
        ]
        for sid in expired_ids:
            self._cache.pop(sid, None)

        logger.info(f"Sesiones expiradas eliminadas: {deleted_count}")
        return deleted_count

    def _get_last_activity(self, session_id: str) -> Optional[str]:
        """Obtiene la última actividad de una sesión."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_activity FROM sessions WHERE session_id = ?", (session_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_active_sessions_count(self) -> int:
        """Obtiene el número de sesiones activas (no expiradas)."""
        timeout_delta = timedelta(hours=self.session_timeout_hours)
        cutoff_time = (datetime.now() - timeout_delta).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM sessions
                WHERE last_activity >= ?
                """,
                (cutoff_time,),
            )
            return cursor.fetchone()[0]
