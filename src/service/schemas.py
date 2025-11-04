from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, description="Consulta en lenguaje natural sobre procesos.")
    metadata_filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filtros opcionales de metadatos para especializar la búsqueda.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="ID de sesión para mantener contexto conversacional (opcional).",
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
    session_id: Optional[str] = None


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


class AnalyticsResponse(BaseModel):
    """Respuesta con métricas de analytics."""

    query_volume: dict[str, Any]
    satisfaction: dict[str, Any]
    top_questions: list[dict[str, Any]]
    top_topics: list[dict[str, Any]]
    response_time: dict[str, Any]
    coverage: dict[str, Any]


class SessionCreateResponse(BaseModel):
    """Respuesta al crear una nueva sesión."""

    session_id: str
    created_at: str


class SessionStatusResponse(BaseModel):
    """Estado de una sesión."""

    session_id: str
    active: bool
    message_count: int


class PredictiveInsightsResponse(BaseModel):
    """Respuesta con insights predictivos y recomendaciones."""

    emerging_topics: list[dict[str, Any]]
    knowledge_gaps: list[dict[str, Any]]
    trending_content: list[dict[str, Any]]
    volume_prediction: dict[str, Any]
    alerts: dict[str, Any]


class RecommendationsResponse(BaseModel):
    """Respuesta con recomendaciones personalizadas."""

    similar_questions: list[dict[str, Any]]
    collaborative_recommendations: list[dict[str, Any]]
    next_steps: list[dict[str, Any]]
