"""Módulo de autenticación y autorización."""

from src.auth.authentication import AuthenticationManager, get_auth_manager
from src.auth.middleware import (
    get_current_admin,
    get_current_data_manager,
    get_current_token,
    get_current_user,
    get_optional_user,
    require_permission,
    security,
)
from src.auth.models import (
    LoginRequest,
    PermissionScope,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenPayload,
    TokenResponse,
    User,
    UserCreate,
    UserResponse,
    UserRole,
)

__all__ = [
    # Autenticación
    "AuthenticationManager",
    "get_auth_manager",
    # Middleware
    "security",
    "get_current_token",
    "get_current_user",
    "get_current_admin",
    "get_current_data_manager",
    "get_optional_user",
    "require_permission",
    # Modelos
    "User",
    "UserCreate",
    "UserResponse",
    "UserRole",
    "TokenPayload",
    "TokenResponse",
    "LoginRequest",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "PermissionScope",
]
