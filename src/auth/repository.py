"""Repositorio para gestionar usuarios en la BD."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import sqlite3

from config.settings import get_settings
from src.auth.authentication import get_auth_manager
from src.auth.models import User, UserCreate, UserRole, UserResponse
from src.security.encryption import EncryptionManager, load_or_create_encryption_key
from src.security.sqlite_cipher import EncryptedSQLiteConnection

logger = logging.getLogger(__name__)


class UserRepository:
    """Repositorio para gestionar usuarios en SQLite."""

    def __init__(self, db_path: Path = None, use_encryption: bool = True):
        """
        Inicializar el repositorio.

        Args:
            db_path: Ruta de la BD (default: desde settings)
            use_encryption: Si True, cifra contraseñas en la BD
        """
        if db_path is None:
            settings = get_settings()
            db_path = settings.auth_db_path

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Inicializar gestor de cifrado
        self.encryption_manager = None
        if use_encryption:
            settings = get_settings()
            if settings.encryption_key:
                try:
                    self.encryption_manager = EncryptionManager(settings.encryption_key)
                    logger.info("Cifrado de BD habilitado")
                except Exception as e:
                    logger.warning(f"No se pudo inicializar cifrado: {e}. Usando sin cifrado.")

        # Inicializar la BD
        self._init_db()

    def _init_db(self):
        """Inicializar la tabla de usuarios si no existe."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT,
                    hashed_password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    created_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email)
                """
            )
            conn.commit()
        logger.info("BD de usuarios inicializada")

    def create_user(self, user_create: UserCreate) -> User:
        """
        Crear un nuevo usuario.

        Args:
            user_create: Datos del usuario a crear

        Returns:
            Usuario creado

        Raises:
            ValueError si el usuario ya existe
        """
        # Verificar que no existe
        if self.get_user_by_username(user_create.username):
            raise ValueError(f"El usuario '{user_create.username}' ya existe")

        if self.get_user_by_email(user_create.email):
            raise ValueError(f"El email '{user_create.email}' ya está registrado")

        # Crear usuario
        user_id = str(uuid.uuid4())
        auth_manager = get_auth_manager()
        hashed_password = auth_manager.hash_password(user_create.password)

        now = datetime.now().isoformat()

        user = User(
            id=user_id,
            username=user_create.username,
            email=user_create.email,
            full_name=user_create.full_name,
            hashed_password=hashed_password,
            role=user_create.role,
            is_active=True,
            created_at=datetime.fromisoformat(now),
            last_login=None,
        )

        # Guardar en BD (con cifrado si está disponible)
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Cifrar contraseña si hay encryption_manager
                hashed_password = user.hashed_password
                if self.encryption_manager:
                    hashed_password = self.encryption_manager.encrypt(hashed_password)

                conn.execute(
                    """
                    INSERT INTO users
                    (id, username, email, full_name, hashed_password, role, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user.id,
                        user.username,
                        user.email,
                        user.full_name,
                        hashed_password,
                        user.role.value,  # Convertir enum a string
                        user.is_active,
                        now,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Error al crear usuario: {e}")

        logger.info(f"Usuario '{user.username}' creado exitosamente")
        return user

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Obtener un usuario por ID.

        Args:
            user_id: ID del usuario

        Returns:
            Usuario si existe, None si no
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_user(row)

        return None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Obtener un usuario por username.

        Args:
            username: Username del usuario

        Returns:
            Usuario si existe, None si no
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_user(row)

        return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Obtener un usuario por email.

        Args:
            email: Email del usuario

        Returns:
            Usuario si existe, None si no
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_user(row)

        return None

    def update_last_login(self, user_id: str) -> bool:
        """
        Actualizar el timestamp del último login.

        Args:
            user_id: ID del usuario

        Returns:
            True si se actualizó
        """
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (now, user_id),
            )
            conn.commit()

            return cursor.rowcount > 0

    def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """
        Listar usuarios con paginación.

        Args:
            skip: Offset
            limit: Límite de resultados

        Returns:
            Lista de usuarios
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, skip),
            )
            rows = cursor.fetchall()

            return [self._row_to_user(row) for row in rows]

    def delete_user(self, user_id: str) -> bool:
        """
        Eliminar un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            True si se eliminó
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM users WHERE id = ?",
                (user_id,),
            )
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Usuario {user_id} eliminado")

            return deleted

    def deactivate_user(self, user_id: str) -> bool:
        """
        Desactivar un usuario (soft delete).

        Args:
            user_id: ID del usuario

        Returns:
            True si se desactivó
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE users SET is_active = 0 WHERE id = ?",
                (user_id,),
            )
            conn.commit()

            deactivated = cursor.rowcount > 0
            if deactivated:
                logger.info(f"Usuario {user_id} desactivado")

            return deactivated

    def _row_to_user(self, row: sqlite3.Row) -> User:
        """
        Convertir una fila de la BD a un objeto User.

        Args:
            row: Fila de sqlite3.Row

        Returns:
            Usuario
        """
        # Descifrar contraseña si está cifrada
        hashed_password = row["hashed_password"]
        if self.encryption_manager and hashed_password:
            try:
                hashed_password = self.encryption_manager.decrypt(hashed_password)
            except Exception:
                # Si falla, usar como está (puede ser que no esté cifrada)
                pass

        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            hashed_password=hashed_password,
            role=UserRole(row["role"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_login=datetime.fromisoformat(row["last_login"]) if row["last_login"] else None,
        )


# Singleton global del repositorio
_user_repository: Optional[UserRepository] = None


def get_user_repository() -> UserRepository:
    """Obtener la instancia del repositorio de usuarios."""
    global _user_repository
    if _user_repository is None:
        _user_repository = UserRepository()
    return _user_repository
