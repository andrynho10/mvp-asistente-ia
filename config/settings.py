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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
