from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, description="Consulta en lenguaje natural sobre procesos.")
    metadata_filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filtros opcionales de metadatos para especializar la búsqueda.",
    )


class SourceReference(BaseModel):
    source: str
    chunk_id: str | None = None
    process: str | None = None
    keywords: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str
    references: list[SourceReference]
    raw_context: str


class FeedbackRequest(BaseModel):
    question: str
    answer: str
    is_helpful: bool
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    status: str


class HealthResponse(BaseModel):
    status: str
    vector_store_ready: bool
