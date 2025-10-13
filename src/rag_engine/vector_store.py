from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


from config.settings import get_settings


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value
        else:
            sanitized[key] = json.dumps(value, ensure_ascii=False)
    return sanitized


def read_chunks(chunks_path: Path) -> Tuple[List[str], List[dict]]:
    texts: List[str] = []
    metadatas: List[dict] = []
    if not chunks_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo procesado: {chunks_path}")

    with chunks_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            payload = json.loads(line)
            text = payload.get("text", "")
            if not text.strip():
                continue
            texts.append(text)
            raw_metadata = payload.get("metadata", {})
            metadatas.append(sanitize_metadata(raw_metadata))
    return texts, metadatas


def resolve_embedding_model(model_name: str) -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=model_name)


def build_vector_store(
    chunks_path: Path | None = None,
    persist_directory: Path | None = None,
    model_name: str | None = None,
    collection_name: str = "organizational-knowledge",
) -> Chroma:
    settings = get_settings()
    chunks_file = chunks_path or settings.knowledge_base_path / "knowledge_chunks.jsonl"
    persist_dir = persist_directory or settings.vector_store_path
    persist_dir.mkdir(parents=True, exist_ok=True)

    embedding_model = model_name or settings.embedding_model
    texts, metadatas = read_chunks(chunks_file)
    embeddings = resolve_embedding_model(embedding_model)

    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )

    if texts:
        vector_store.add_texts(texts=texts, metadatas=metadatas)
    return vector_store


def load_vector_store(
    persist_directory: Path | None = None,
    model_name: str | None = None,
    collection_name: str = "organizational-knowledge",
) -> Chroma:
    settings = get_settings()
    persist_dir = persist_directory or settings.vector_store_path
    embedding_model = model_name or settings.embedding_model
    embeddings = resolve_embedding_model(embedding_model)

    return Chroma(
        collection_name=collection_name,
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
    )
