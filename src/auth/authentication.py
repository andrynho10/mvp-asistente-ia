"""Módulo de autenticación JWT."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError

from config.settings import get_settings
from src.auth.models import TokenPayload, User, UserRole

logger = logging.getLogger(__name__)

# Configurar contexto de hash de passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthenticationManager:
    """Gestor centralizado de autenticación."""

    def __init__(self):
        """Inicializar el gestor de autenticación."""
        self.settings = get_settings()
        self.algorithm = "HS256"
        self.secret_key = self.settings.secret_key

    def hash_password(self, password: str) -> str:
        """
        Hashear un password.

        Args:
            password: Password en texto plano

        Returns:
            Password hasheado
        """
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verificar un password contra su hash.

        Args:
            plain_password: Password en texto plano
            hashed_password: Password hasheado

        Returns:
            True si el password es correcto
        """
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self,
        user: User,
        expires_delta: Optional[timedelta] = None,
    ) -> tuple[str, int]:
        """
        Crear un token de acceso JWT.

        Args:
            user: Usuario para el que crear el token
            expires_delta: Tiempo de expiración personalizado (default: settings)

        Returns:
            Tupla (token, expires_in_seconds)
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.settings.access_token_expire_minutes)

        # Calcular tiempos
        now = datetime.utcnow()
        expire = now + expires_delta
        iat = int(now.timestamp())
        exp = int(expire.timestamp())
        expires_in = int(expires_delta.total_seconds())

        # Crear payload
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "iat": iat,
            "exp": exp,
        }

        # Codificar token
        encoded_jwt = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        logger.info(f"Token creado para usuario {user.username} (expira en {expires_in}s)")

        return encoded_jwt, expires_in

    def create_refresh_token(
        self,
        user: User,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Crear un token de refresco JWT.

        Args:
            user: Usuario para el que crear el token
            expires_delta: Tiempo de expiración personalizado (default: settings)

        Returns:
            Token de refresco
        """
        if expires_delta is None:
            expires_delta = timedelta(
                minutes=self.settings.refresh_token_expire_minutes
            )

        # Calcular tiempos
        now = datetime.utcnow()
        expire = now + expires_delta
        iat = int(now.timestamp())
        exp = int(expire.timestamp())

        # Crear payload (más simple que access token)
        payload = {
            "sub": user.id,
            "type": "refresh",
            "iat": iat,
            "exp": exp,
        }

        # Codificar token
        encoded_jwt = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        logger.debug(f"Refresh token creado para usuario {user.username}")

        return encoded_jwt

    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """
        Verificar y decodificar un token JWT.

        Args:
            token: Token a verificar

        Returns:
            TokenPayload si es válido, None si no
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Validar estructura esperada
            token_payload = TokenPayload(**payload)

            return token_payload

        except JWTError as e:
            logger.warning(f"Error al decodificar token: {e}")
            return None
        except ValidationError as e:
            logger.warning(f"Error en validación del payload: {e}")
            return None

    def verify_refresh_token(self, token: str) -> Optional[str]:
        """
        Verificar un token de refresco y extraer el user_id.

        Args:
            token: Refresh token a verificar

        Returns:
            User ID si es válido, None si no
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Validar que sea un refresh token
            if payload.get("type") != "refresh":
                logger.warning("Token no es un refresh token válido")
                return None

            user_id = payload.get("sub")
            if not user_id:
                logger.warning("Refresh token sin 'sub' (user_id)")
                return None

            return user_id

        except JWTError as e:
            logger.warning(f"Error al verificar refresh token: {e}")
            return None

    def is_token_expired(self, token: str) -> bool:
        """
        Verificar si un token ha expirado.

        Args:
            token: Token a verificar

        Returns:
            True si el token ha expirado
        """
        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm], options={"verify_exp": False}
            )
            exp = payload.get("exp")
            if not exp:
                return True

            now = datetime.utcnow().timestamp()
            return now > exp

        except JWTError:
            return True


# Singleton global para el gestor de autenticación
_auth_manager: Optional[AuthenticationManager] = None


def get_auth_manager() -> AuthenticationManager:
    """Obtener la instancia del gestor de autenticación."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthenticationManager()
    return _auth_manager
