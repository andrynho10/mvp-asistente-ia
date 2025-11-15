from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b-instruct-q4_K_M", alias="OLLAMA_MODEL")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL"
    )
    vector_store_path: Path = Field(default=Path("data/embeddings/chroma"), alias="VECTOR_STORE_PATH")
    knowledge_base_path: Path = Field(default=Path("data/processed"), alias="KNOWLEDGE_BASE_PATH")
    raw_data_path: Path = Field(default=Path("data/raw"), alias="RAW_DATA_PATH")
    analytics_db_path: Path = Field(default=Path("data/analytics/analytics.db"), alias="ANALYTICS_DB_PATH")
    sessions_db_path: Path = Field(default=Path("data/sessions/sessions.db"), alias="SESSIONS_DB_PATH")
    session_timeout_hours: int = Field(default=24, alias="SESSION_TIMEOUT_HOURS")
    service_host: str = Field(default="0.0.0.0", alias="SERVICE_HOST")
    service_port: int = Field(default=8000, alias="SERVICE_PORT")
    streamlit_port: int = Field(default=8501, alias="STREAMLIT_PORT")
    allowed_origins: str = Field(default="http://localhost:8501", alias="ALLOWED_ORIGINS")
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")

    # Configuración de Autenticación (RS1, RS2)
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        alias="SECRET_KEY",
        description="Llave secreta para JWT (CAMBIAR EN PRODUCCIÓN)"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        description="Minutos antes de que expire el access token"
    )
    refresh_token_expire_minutes: int = Field(
        default=10080,  # 7 días
        alias="REFRESH_TOKEN_EXPIRE_MINUTES",
        description="Minutos antes de que expire el refresh token"
    )
    auth_db_path: Path = Field(
        default=Path("data/auth/auth.db"),
        alias="AUTH_DB_PATH",
        description="Ruta de la BD de autenticación"
    )

    # Configuración de Cifrado (RS4)
    encryption_key: str = Field(
        default="",  # Debe ser generada o cargada desde .env
        alias="ENCRYPTION_KEY",
        description="Llave Fernet para cifrado de datos sensibles (generar con cryptography.fernet.Fernet.generate_key())"
    )
    enable_db_encryption: bool = Field(
        default=True,
        alias="ENABLE_DB_ENCRYPTION",
        description="Activar cifrado en bases de datos"
    )
    encrypted_keys_path: Path = Field(
        default=Path("data/encrypted_keys"),
        alias="ENCRYPTED_KEYS_PATH",
        description="Directorio para almacenar claves de cifrado"
    )
    ssl_enabled: bool = Field(
        default=False,
        alias="SSL_ENABLED",
        description="Activar HTTPS/SSL en desarrollo. En producción usar nginx/reverse proxy"
    )
    ssl_certfile: Path | None = Field(
        default=None,
        alias="SSL_CERTFILE",
        description="Ruta al certificado SSL (para desarrollo)"
    )
    ssl_keyfile: Path | None = Field(
        default=None,
        alias="SSL_KEYFILE",
        description="Ruta a la llave privada SSL (para desarrollo)"
    )

    # Configuración de Confidencialidad y GDPR (RS5)
    enable_pii_masking: bool = Field(
        default=True,
        alias="ENABLE_PII_MASKING",
        description="Activar enmascaramiento automático de PII en logs"
    )
    pii_masking_strategy: str = Field(
        default="redact",
        alias="PII_MASKING_STRATEGY",
        description="Estrategia de enmascaramiento: 'redact', 'hash', 'partial', 'replace'"
    )
    enable_data_retention: bool = Field(
        default=True,
        alias="ENABLE_DATA_RETENTION",
        description="Activar políticas de retención de datos"
    )
    session_retention_days: int = Field(
        default=30,
        alias="SESSION_RETENTION_DAYS",
        description="Días para retener datos de sesión"
    )
    analytics_retention_days: int = Field(
        default=90,
        alias="ANALYTICS_RETENTION_DAYS",
        description="Días para retener datos de análisis"
    )
    activity_log_retention_days: int = Field(
        default=180,
        alias="ACTIVITY_LOG_RETENTION_DAYS",
        description="Días para retener logs de actividad"
    )
    auth_log_retention_days: int = Field(
        default=365,
        alias="AUTH_LOG_RETENTION_DAYS",
        description="Días para retener logs de autenticación (auditoria)"
    )
    audit_db_path: Path = Field(
        default=Path("data/audit/retention_audit.db"),
        alias="AUDIT_DB_PATH",
        description="Ruta de la BD de auditoría de retención"
    )
    logs_dir: Path = Field(
        default=Path("logs"),
        alias="LOGS_DIR",
        description="Directorio para almacenar logs"
    )
    enable_structured_logging: bool = Field(
        default=True,
        alias="ENABLE_STRUCTURED_LOGGING",
        description="Usar formato JSON para logs estructurados"
    )
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    # GDPR/Ley 19.628 - Derechos del usuario
    enable_gdpr_features: bool = Field(
        default=True,
        alias="ENABLE_GDPR_FEATURES",
        description="Activar características de GDPR/Ley 19.628"
    )
    user_consent_required: bool = Field(
        default=True,
        alias="USER_CONSENT_REQUIRED",
        description="Requerir consentimiento explícito antes de procesar datos"
    )
    allow_data_export: bool = Field(
        default=True,
        alias="ALLOW_DATA_EXPORT",
        description="Permitir a usuarios exportar sus datos"
    )
    allow_data_deletion: bool = Field(
        default=True,
        alias="ALLOW_DATA_DELETION",
        description="Permitir a usuarios eliminar sus datos (derecho al olvido)"
    )
    deletion_grace_period_days: int = Field(
        default=30,
        alias="DELETION_GRACE_PERIOD_DAYS",
        description="Días de período de gracia antes de eliminar permanentemente"
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
