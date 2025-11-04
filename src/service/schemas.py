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


# --- Admin API Schemas ---


class DocumentUploadResponse(BaseModel):
    """Respuesta al subir un documento."""

    id: str
    filename: str
    size_bytes: int
    uploaded_at: str
    status: str = "active"


class DocumentInfo(BaseModel):
    """Información de un documento."""

    id: str
    filename: str
    size_bytes: int
    uploaded_at: str
    file_hash: str
    status: str


class DocumentListResponse(BaseModel):
    """Respuesta con lista de documentos."""

    documents: list[DocumentInfo]
    total: int


class DocumentDeleteResponse(BaseModel):
    """Respuesta al eliminar un documento."""

    status: str
    doc_id: str
    filename: str


class IngestionStatusResponse(BaseModel):
    """Estado del proceso de ingesta."""

    status: str
    message: str
    documents_processed: Optional[int] = None
    time_taken_seconds: Optional[float] = None


class DocumentStatsResponse(BaseModel):
    """Estadísticas del sistema de documentos."""

    total_documents: int
    deleted_documents: int
    total_size_bytes: int
    total_size_mb: float
    last_updated: Optional[str]
    last_ingestion: Optional[str]


class FeedbackItem(BaseModel):
    """Item de feedback para revisión."""

    id: int
    query_id: int
    question: str
    comment: Optional[str]
    timestamp: str
    category: Optional[str]
    status: str
    action_notes: Optional[str]


class FeedbackListResponse(BaseModel):
    """Respuesta con lista de feedback."""

    feedback: list[FeedbackItem]
    total: int


class FeedbackCategorizeRequest(BaseModel):
    """Request para categorizar feedback."""

    category: str = Field(..., description="missing_info, incorrect_answer, unclear, other")


class FeedbackActionRequest(BaseModel):
    """Request para marcar feedback como accionado."""

    action_notes: str = Field(..., min_length=5, description="Notas sobre la acción tomada")


class FeedbackStatsResponse(BaseModel):
    """Estadísticas de feedback."""

    total_feedback: int
    negative_feedback: int
    positive_feedback: int
    by_category: dict[str, int]
    by_status: dict[str, int]
    pending_review: int
    actioned: int
    top_issues: list[dict[str, Any]]
