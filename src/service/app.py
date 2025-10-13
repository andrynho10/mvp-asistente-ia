from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain.schema import Document
from langchain_community.vectorstores import Chroma

from config.settings import get_settings
from src.rag_engine import ask_question, load_vector_store
from src.service.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SourceReference,
)


settings = get_settings()
app = FastAPI(title="Asistente Organizacional", version="0.1.0")

origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cached_vector_store: Optional[Chroma] = None


def vector_store_ready() -> bool:
    persist_dir = settings.vector_store_path
    return persist_dir.exists() and any(persist_dir.iterdir())


def get_vector_store() -> Chroma:
    global _cached_vector_store
    if _cached_vector_store is None:
        if not vector_store_ready():
            raise RuntimeError("El vector store no se ha inicializado. Ejecute la ingesta primero.")
        _cached_vector_store = load_vector_store()
    return _cached_vector_store


def render_references(documents: list[Document]) -> list[SourceReference]:
    references = []
    for doc in documents:
        metadata = doc.metadata or {}
        references.append(
            SourceReference(
                source=str(metadata.get("source", "desconocido")),
                chunk_id=metadata.get("chunk_id"),
                process=metadata.get("process"),
                keywords=metadata.get("keywords", []),
            )
        )
    return references


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", vector_store_ready=vector_store_ready())


@app.post("/ask", response_model=QueryResponse)
def ask(request: QueryRequest, vector_store: Chroma = Depends(get_vector_store)) -> QueryResponse:
    if len(request.question.strip()) < 5:
        raise HTTPException(status_code=400, detail="La pregunta es demasiado corta.")

    response = ask_question(
        vector_store=vector_store,
        question=request.question,
        metadata_filters=request.metadata_filters,
    )
    answer = response.get("answer", "")
    source_documents = response.get("source_documents", [])
    references = render_references(source_documents)

    return QueryResponse(answer=answer, references=references, raw_context=response["context_rendered"])


def get_feedback_path() -> Path:
    feedback_dir = Path("data") / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    return feedback_dir / "feedback.jsonl"


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(payload: FeedbackRequest) -> FeedbackResponse:
    feedback_path = get_feedback_path()
    record = payload.model_dump()
    record["status"] = "recorded"
    with feedback_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")
    return FeedbackResponse(status="recorded")
