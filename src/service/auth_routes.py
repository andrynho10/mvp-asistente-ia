"""Rutas de autenticación para FastAPI."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth import (
    AuthenticationManager,
    LoginRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
    get_auth_manager,
    get_current_user,
)
from src.auth.repository import get_user_repository

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_create: UserCreate,
    user_repo=Depends(get_user_repository),
) -> UserResponse:
    """
    Registrar un nuevo usuario.

    Args:
        user_create: Datos del usuario a crear

    Returns:
        Información del usuario creado

    Raises:
        HTTPException si el usuario ya existe
    """
    try:
        user = user_repo.create_user(user_create)
        logger.info(f"Usuario '{user.username}' registrado exitosamente")
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
        logger.warning(f"Error al registrar usuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@auth_router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    auth_manager: AuthenticationManager = Depends(get_auth_manager),
    user_repo=Depends(get_user_repository),
) -> TokenResponse:
    """
    Login de usuario.

    Args:
        request: Credenciales de login
        auth_manager: Gestor de autenticación
        user_repo: Repositorio de usuarios

    Returns:
        Token de acceso y información del usuario

    Raises:
        HTTPException si las credenciales son inválidas
    """
    # Obtener usuario por username o email
    user = user_repo.get_user_by_username(request.username)
    if not user:
        user = user_repo.get_user_by_email(request.username)

    if not user:
        logger.warning(f"Intento de login fallido: usuario '{request.username}' no encontrado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    # Verificar contraseña
    if not auth_manager.verify_password(request.password, user.hashed_password):
        logger.warning(f"Intento de login fallido: password incorrecto para '{user.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    # Verificar que el usuario está activo
    if not user.is_active:
        logger.warning(f"Intento de login fallido: usuario '{user.username}' está desactivado")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado",
        )

    # Crear tokens
    access_token, expires_in = auth_manager.create_access_token(user)

    # Actualizar último login
    user_repo.update_last_login(user.id)

    logger.info(f"Login exitoso para usuario '{user.username}'")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            role=user.role,
            created_at=user.created_at,
            last_login=user.last_login,
        ),
    )


@auth_router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(
    request: RefreshTokenRequest,
    auth_manager: AuthenticationManager = Depends(get_auth_manager),
    user_repo=Depends(get_user_repository),
) -> RefreshTokenResponse:
    """
    Refrescar el access token usando un refresh token.

    Args:
        request: Refresh token
        auth_manager: Gestor de autenticación
        user_repo: Repositorio de usuarios

    Returns:
        Nuevo access token

    Raises:
        HTTPException si el refresh token es inválido
    """
    # Verificar refresh token
    user_id = auth_manager.verify_refresh_token(request.refresh_token)

    if not user_id:
        logger.warning("Intento de refresh con token inválido")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )

    # Obtener usuario
    user = user_repo.get_user_by_id(user_id)

    if not user or not user.is_active:
        logger.warning(f"Refresh token inválido para usuario {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado",
        )

    # Crear nuevo access token
    access_token, expires_in = auth_manager.create_access_token(user)

    logger.debug(f"Token refrescado para usuario '{user.username}'")

    return RefreshTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@auth_router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    user_repo=Depends(get_user_repository),
) -> UserResponse:
    """
    Obtener la información del usuario actual.

    Args:
        current_user: Usuario actual del token
        user_repo: Repositorio de usuarios

    Returns:
        Información del usuario actual

    Raises:
        HTTPException si el usuario no se encuentra
    """
    user = user_repo.get_user_by_id(current_user["user_id"])

    if not user:
        logger.warning(f"Usuario {current_user['user_id']} no encontrado")
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
