"""Middleware de autenticación para FastAPI."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.authentication import get_auth_manager
from src.auth.models import PermissionScope, TokenPayload, User, UserRole

logger = logging.getLogger(__name__)

# Esquema de seguridad
security = HTTPBearer()


async def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """
    Obtener el token actual del header Authorization.

    Args:
        credentials: Credenciales HTTP Bearer

    Returns:
        TokenPayload si es válido

    Raises:
        HTTPException si el token es inválido o ha expirado
    """
    token = credentials.credentials
    auth_manager = get_auth_manager()

    # Verificar token
    payload = auth_manager.verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user(
    token_payload: TokenPayload = Depends(get_current_token),
) -> dict:
    """
    Obtener el usuario actual desde el token.

    Args:
        token_payload: Payload del token

    Returns:
        Dict con información del usuario

    Raises:
        HTTPException si el usuario no existe
    """
    # En una app real, aquí se consultaría la BD para obtener usuario actual
    # Por ahora, retornamos la info del token
    return {
        "user_id": token_payload.sub,
        "username": token_payload.username,
        "role": token_payload.role,
    }


async def get_current_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Verificar que el usuario actual es admin.

    Args:
        current_user: Usuario actual

    Returns:
        Usuario actual si es admin

    Raises:
        HTTPException si no es admin
    """
    if current_user["role"] != UserRole.ADMIN:
        logger.warning(
            f"Acceso denegado a admin para usuario {current_user['username']} (rol: {current_user['role']})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )

    return current_user


async def get_current_data_manager(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Verificar que el usuario actual es data_manager o admin.

    Args:
        current_user: Usuario actual

    Returns:
        Usuario actual si tiene permisos

    Raises:
        HTTPException si no tiene permisos
    """
    if current_user["role"] not in [UserRole.ADMIN, UserRole.DATA_MANAGER]:
        logger.warning(
            f"Acceso denegado a data_manager para usuario {current_user['username']} (rol: {current_user['role']})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de data_manager",
        )

    return current_user


def require_permission(permission: PermissionScope):
    """
    Factory para crear dependency que requiere un permiso específico.

    Args:
        permission: Permiso requerido

    Returns:
        Función que verifica el permiso
    """

    async def check_permission(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        """Verificar que el usuario tiene el permiso."""
        from src.auth.models import ROLE_PERMISSIONS

        user_role = current_user["role"]
        allowed_permissions = ROLE_PERMISSIONS.get(user_role, [])

        if permission not in allowed_permissions:
            logger.warning(
                f"Permiso {permission} denegado para usuario {current_user['username']} "
                f"(rol: {user_role})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: {permission}",
            )

        return current_user

    return check_permission


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """
    Obtener usuario actual si está autenticado (opcional).

    Args:
        credentials: Credenciales HTTP Bearer (opcional)

    Returns:
        Dict con información del usuario o None
    """
    if credentials is None:
        return None

    token = credentials.credentials
    auth_manager = get_auth_manager()

    # Verificar token
    payload = auth_manager.verify_token(token)

    if payload is None:
        return None

    # En una app real, aquí se consultaría la BD
    return {
        "user_id": payload.sub,
        "username": payload.username,
        "role": payload.role,
    }
