"""Rutas de gestión de usuarios para administradores."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth import (
    UserResponse,
    UserRole,
    get_current_admin,
)
from src.auth.models import UserCreate
from src.auth.repository import get_user_repository

logger = logging.getLogger(__name__)

users_router = APIRouter(prefix="/users", tags=["user-management"])


@users_router.get("", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_admin: dict = Depends(get_current_admin),
    user_repo=Depends(get_user_repository),
) -> list[UserResponse]:
    """
    Listar todos los usuarios (requiere admin).

    Args:
        skip: Offset para paginación
        limit: Límite de resultados
        current_admin: Admin actual
        user_repo: Repositorio de usuarios

    Returns:
        Lista de usuarios
    """
    try:
        users = user_repo.list_users(skip=skip, limit=limit)
        return [
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                role=user.role,
                created_at=user.created_at,
                last_login=user.last_login,
            )
            for user in users
        ]
    except Exception as e:
        logger.error(f"Error al listar usuarios: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al listar usuarios",
        ) from e


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_create: UserCreate,
    current_admin: dict = Depends(get_current_admin),
    user_repo=Depends(get_user_repository),
) -> UserResponse:
    """
    Crear un nuevo usuario (requiere admin).

    Args:
        user_create: Datos del usuario
        current_admin: Admin actual
        user_repo: Repositorio de usuarios

    Returns:
        Usuario creado
    """
    try:
        user = user_repo.create_user(user_create)
        logger.info(f"Usuario '{user.username}' creado por admin {current_admin['username']}")
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            role=user.role,
            created_at=user.created_at,
            last_login=user.last_login,
        )
    except ValueError as e:
        logger.warning(f"Error al crear usuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error al crear usuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear usuario",
        ) from e


@users_router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    current_admin: dict = Depends(get_current_admin),
    user_repo=Depends(get_user_repository),
) -> UserResponse:
    """
    Obtener un usuario por ID (requiere admin).

    Args:
        user_id: ID del usuario
        current_admin: Admin actual
        user_repo: Repositorio de usuarios

    Returns:
        Información del usuario
    """
    user = user_repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        role=user.role,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@users_router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: str,
    new_role: UserRole,
    current_admin: dict = Depends(get_current_admin),
    user_repo=Depends(get_user_repository),
) -> UserResponse:
    """
    Actualizar el rol de un usuario (requiere admin).

    Args:
        user_id: ID del usuario
        new_role: Nuevo rol
        current_admin: Admin actual
        user_repo: Repositorio de usuarios

    Returns:
        Usuario actualizado
    """
    user = user_repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Actualizar rol en BD
    try:
        import sqlite3

        with sqlite3.connect(user_repo.db_path) as conn:
            conn.execute(
                "UPDATE users SET role = ? WHERE id = ?",
                (new_role.value, user_id),
            )
            conn.commit()

        logger.info(
            f"Rol de usuario '{user.username}' actualizado a {new_role.value} por admin {current_admin['username']}"
        )

        # Recargar usuario
        updated_user = user_repo.get_user_by_id(user_id)

        return UserResponse(
            id=updated_user.id,
            username=updated_user.username,
            email=updated_user.email,
            full_name=updated_user.full_name,
            is_active=updated_user.is_active,
            role=updated_user.role,
            created_at=updated_user.created_at,
            last_login=updated_user.last_login,
        )
    except Exception as e:
        logger.error(f"Error al actualizar rol: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar rol",
        ) from e


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: str,
    current_admin: dict = Depends(get_current_admin),
    user_repo=Depends(get_user_repository),
) -> None:
    """
    Desactivar un usuario (requiere admin).

    Args:
        user_id: ID del usuario
        current_admin: Admin actual
        user_repo: Repositorio de usuarios
    """
    user = user_repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Prevenir que el admin se desactive a sí mismo
    if user_id == current_admin["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivarte a ti mismo",
        )

    if user_repo.deactivate_user(user_id):
        logger.info(
            f"Usuario '{user.username}' desactivado por admin {current_admin['username']}"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al desactivar usuario",
        )
