"""Modelos de autenticación y autorización."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """Roles disponibles en el sistema."""

    ADMIN = "admin"
    DATA_MANAGER = "data_manager"
    USER = "user"
    GUEST = "guest"


class User(BaseModel):
    """Modelo de usuario del sistema."""

    id: str = Field(..., description="ID único del usuario")
    username: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario")
    email: EmailStr = Field(..., description="Email del usuario")
    full_name: Optional[str] = Field(None, description="Nombre completo")
    is_active: bool = Field(default=True, description="Si el usuario está activo")
    role: UserRole = Field(default=UserRole.USER, description="Rol del usuario")
    created_at: datetime = Field(default_factory=datetime.now, description="Fecha de creación")
    last_login: Optional[datetime] = Field(None, description="Último login")
    hashed_password: str = Field(..., description="Password hasheado (no exponer)")

    class Config:
        """Configuración del modelo."""

        from_attributes = True


class UserCreate(BaseModel):
    """Modelo para crear un usuario."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password sin hashear")
    full_name: Optional[str] = None
    role: UserRole = Field(default=UserRole.USER)


class UserResponse(BaseModel):
    """Modelo de respuesta de usuario (sin password)."""

    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        """Configuración del modelo."""

        from_attributes = True


class TokenPayload(BaseModel):
    """Payload del token JWT."""

    sub: str = Field(..., description="Subject (user_id)")
    username: str
    role: UserRole
    exp: int = Field(..., description="Expiration time (Unix timestamp)")
    iat: int = Field(..., description="Issued at (Unix timestamp)")


class TokenResponse(BaseModel):
    """Respuesta de login con token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: UserResponse


class LoginRequest(BaseModel):
    """Modelo para login."""

    username: str = Field(..., description="Username o email")
    password: str = Field(..., description="Password")


class RefreshTokenRequest(BaseModel):
    """Modelo para refrescar token."""

    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Respuesta de refresh token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PermissionScope(str, Enum):
    """Permisos disponibles por función."""

    # Queries
    QUERY_READ = "query:read"
    QUERY_WRITE = "query:write"

    # Documents
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"

    # Analytics
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_WRITE = "analytics:write"

    # Admin
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_DELETE = "admin:delete"

    # User Management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"


# Mapeo de roles a permisos
ROLE_PERMISSIONS: dict[UserRole, list[PermissionScope]] = {
    UserRole.ADMIN: list(PermissionScope),  # Admin tiene todos los permisos
    UserRole.DATA_MANAGER: [
        PermissionScope.QUERY_READ,
        PermissionScope.QUERY_WRITE,
        PermissionScope.DOCUMENT_READ,
        PermissionScope.DOCUMENT_WRITE,
        PermissionScope.ANALYTICS_READ,
        PermissionScope.ADMIN_READ,
    ],
    UserRole.USER: [
        PermissionScope.QUERY_READ,
        PermissionScope.QUERY_WRITE,
        PermissionScope.DOCUMENT_READ,
        PermissionScope.ANALYTICS_READ,
    ],
    UserRole.GUEST: [
        PermissionScope.QUERY_READ,
        PermissionScope.DOCUMENT_READ,
    ],
}
