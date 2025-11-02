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
    service_host: str = Field(default="0.0.0.0", alias="SERVICE_HOST")
    service_port: int = Field(default=8000, alias="SERVICE_PORT")
    streamlit_port: int = Field(default=8501, alias="STREAMLIT_PORT")
    allowed_origins: str = Field(default="http://localhost:8501", alias="ALLOWED_ORIGINS")
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
