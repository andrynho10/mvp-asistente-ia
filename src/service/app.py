from __future__ import annotations

import json
import logging
import time
import traceback
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.documents import Document
from langchain_chroma import Chroma

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config.settings import get_settings
from src.analytics import AnalyticsTracker, MetricsCalculator
from src.memory import SessionManager
from src.predictive import PatternAnalyzer, Recommender, AnomalyDetector
from src.rag_engine import ask_question, load_vector_store
from src.service.admin_routes import admin_router
from src.service.schemas import (
    AnalyticsResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    PredictiveInsightsResponse,
    QueryRequest,
    QueryResponse,
    RecommendationsResponse,
    SessionCreateResponse,
    SessionStatusResponse,
    SourceReference,
)


settings = get_settings()
app = FastAPI(title="Asistente Organizacional", version="0.1.0")

# Incluir rutas de administración
app.include_router(admin_router)

origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cached_vector_store: Optional[Chroma] = None
_analytics_tracker: Optional[AnalyticsTracker] = None
_session_manager: Optional[SessionManager] = None


def get_analytics_tracker() -> AnalyticsTracker:
    """Obtiene la instancia del tracker de analytics."""
    global _analytics_tracker
    if _analytics_tracker is None:
        _analytics_tracker = AnalyticsTracker(settings.analytics_db_path)
    return _analytics_tracker


def get_session_manager() -> SessionManager:
    """Obtiene la instancia del gestor de sesiones."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(
            db_path=settings.sessions_db_path,
            session_timeout_hours=settings.session_timeout_hours,
        )
    return _session_manager


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

        # Deserializar keywords si están en formato JSON string
        keywords = metadata.get("keywords", [])
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except (json.JSONDecodeError, TypeError):
                keywords = []

        references.append(
            SourceReference(
                source=str(metadata.get("source", "desconocido")),
                chunk_id=metadata.get("chunk_id"),
                process=metadata.get("process"),
                keywords=keywords if isinstance(keywords, list) else [],
            )
        )
    return references


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", vector_store_ready=vector_store_ready())


@app.post("/ask", response_model=QueryResponse)
def ask(
    request: QueryRequest,
    vector_store: Chroma = Depends(get_vector_store),
    tracker: AnalyticsTracker = Depends(get_analytics_tracker),
    session_manager: SessionManager = Depends(get_session_manager),
) -> QueryResponse:
    logger.info(f"Recibida pregunta: {request.question[:50]}...")

    if len(request.question.strip()) < 5:
        raise HTTPException(status_code=400, detail="La pregunta es demasiado corta.")

    start_time = time.time()
    error_msg = None

    # Obtener o crear memoria conversacional
    conversation_memory = None
    session_id = request.session_id

    if session_id:
        conversation_memory = session_manager.get_session(session_id)
        if conversation_memory is None:
            logger.warning(f"Sesión {session_id} no encontrada o expirada. Continuando sin memoria.")
            session_id = None

    try:
        logger.info("Llamando a ask_question...")
        response = ask_question(
            vector_store=vector_store,
            question=request.question,
            metadata_filters=request.metadata_filters,
            conversation_memory=conversation_memory,
        )
        logger.info("ask_question completado exitosamente")

        # Guardar memoria actualizada si existe
        if conversation_memory:
            session_manager.save_session(conversation_memory)
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"Error en ask_question: {exc}")
        logger.error(traceback.format_exc())

        # Track error
        response_time = (time.time() - start_time) * 1000
        tracker.track_query(
            question=request.question,
            answer="",
            references=[],
            metadata_filters=request.metadata_filters,
            response_time_ms=response_time,
            error=error_msg,
        )

        raise HTTPException(status_code=502, detail=f"Error al consultar el modelo: {exc}") from exc

    try:
        answer = response.get("answer", "")
        source_documents = response.get("source_documents", [])
        references = render_references(source_documents)
        logger.info(f"Respuesta generada exitosamente, {len(references)} referencias")

        # Calcular tiempo de respuesta
        response_time = (time.time() - start_time) * 1000

        # Track query exitosa
        tracker.track_query(
            question=request.question,
            answer=answer,
            references=[ref.model_dump() for ref in references],
            metadata_filters=request.metadata_filters,
            response_time_ms=response_time,
            session_id=session_id,
        )

        return QueryResponse(
            answer=answer,
            references=references,
            raw_context=response["context_rendered"],
            session_id=session_id,
        )
    except Exception as exc:
        logger.error(f"Error al construir respuesta: {exc}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error al procesar respuesta: {exc}") from exc


def get_feedback_path() -> Path:
    feedback_dir = Path("data") / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    return feedback_dir / "feedback.jsonl"


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(
    payload: FeedbackRequest,
    tracker: AnalyticsTracker = Depends(get_analytics_tracker),
) -> FeedbackResponse:
    # Mantener compatibilidad con el archivo JSONL existente
    feedback_path = get_feedback_path()
    record = payload.model_dump()
    record["status"] = "recorded"
    with feedback_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Track en la base de datos de analytics
    tracker.track_feedback(
        question=payload.question,
        answer=payload.answer,
        is_helpful=payload.is_helpful,
        comment=payload.comment,
    )

    return FeedbackResponse(status="recorded")


@app.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(days: int = 7) -> AnalyticsResponse:
    """
    Obtiene métricas de analytics para el período especificado.

    Args:
        days: Número de días a analizar (default: 7)
    """
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="El parámetro 'days' debe estar entre 1 y 365.")

    calculator = MetricsCalculator(settings.analytics_db_path)

    try:
        summary = calculator.get_dashboard_summary(days)
        return AnalyticsResponse(**summary)
    except Exception as exc:
        logger.error(f"Error al calcular analytics: {exc}")
        raise HTTPException(status_code=500, detail=f"Error al calcular métricas: {exc}") from exc


@app.post("/sessions", response_model=SessionCreateResponse)
def create_session(
    max_history: int = 5,
    session_manager: SessionManager = Depends(get_session_manager),
) -> SessionCreateResponse:
    """
    Crea una nueva sesión conversacional.

    Args:
        max_history: Número de intercambios a recordar (default: 5)

    Returns:
        SessionCreateResponse con session_id y timestamp
    """
    from datetime import datetime

    session_id = session_manager.create_session(max_history=max_history)
    return SessionCreateResponse(session_id=session_id, created_at=datetime.now().isoformat())


@app.get("/sessions/{session_id}", response_model=SessionStatusResponse)
def get_session_status(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> SessionStatusResponse:
    """
    Obtiene el estado de una sesión.

    Args:
        session_id: ID de la sesión

    Returns:
        SessionStatusResponse con estado y número de mensajes
    """
    memory = session_manager.get_session(session_id)

    if memory is None:
        return SessionStatusResponse(session_id=session_id, active=False, message_count=0)

    return SessionStatusResponse(
        session_id=session_id, active=True, message_count=len(memory.messages)
    )


@app.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, str]:
    """
    Elimina una sesión.

    Args:
        session_id: ID de la sesión a eliminar

    Returns:
        Mensaje de confirmación
    """
    session_manager.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.get("/predictive/insights", response_model=PredictiveInsightsResponse)
def get_predictive_insights(days: int = 7) -> PredictiveInsightsResponse:
    """
    Obtiene insights predictivos y análisis de tendencias.

    Args:
        days: Número de días a analizar (default: 7)

    Returns:
        Insights con temas emergentes, gaps, predicciones y alertas
    """
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="El parámetro 'days' debe estar entre 1 y 90.")

    analyzer = PatternAnalyzer(settings.analytics_db_path)
    recommender = Recommender(settings.analytics_db_path)
    detector = AnomalyDetector(settings.analytics_db_path)

    try:
        insights = {
            "emerging_topics": analyzer.get_emerging_topics(days=days),
            "knowledge_gaps": analyzer.detect_knowledge_gaps(days=days),
            "trending_content": recommender.get_trending_content(days=days),
            "volume_prediction": analyzer.predict_future_volume(days_ahead=7, historical_days=days),
            "alerts": detector.get_all_alerts(days=days),
        }
        return PredictiveInsightsResponse(**insights)
    except Exception as exc:
        logger.error(f"Error al calcular insights predictivos: {exc}")
        raise HTTPException(status_code=500, detail=f"Error al calcular insights: {exc}") from exc


@app.get("/predictive/recommendations", response_model=RecommendationsResponse)
def get_recommendations(question: str, limit: int = 5) -> RecommendationsResponse:
    """
    Obtiene recomendaciones contextuales para una pregunta.

    Args:
        question: Pregunta de referencia
        limit: Número máximo de recomendaciones por categoría

    Returns:
        Recomendaciones de preguntas similares, colaborativas y próximos pasos
    """
    if len(question.strip()) < 5:
        raise HTTPException(status_code=400, detail="La pregunta es demasiado corta.")

    recommender = Recommender(settings.analytics_db_path)

    try:
        recommendations = {
            "similar_questions": recommender.get_similar_questions(question, limit=limit),
            "collaborative_recommendations": recommender.get_collaborative_recommendations(
                question, limit=limit
            ),
            "next_steps": [],  # Se calculará basándose en el topic actual
        }

        return RecommendationsResponse(**recommendations)
    except Exception as exc:
        logger.error(f"Error al generar recomendaciones: {exc}")
        raise HTTPException(status_code=500, detail=f"Error al generar recomendaciones: {exc}") from exc


@app.get("/predictive/alerts")
def get_alerts() -> dict[str, Any]:
    """
    Obtiene todas las alertas y anomalías detectadas.

    Returns:
        Dict con alertas categorizadas por tipo
    """
    detector = AnomalyDetector(settings.analytics_db_path)

    try:
        return detector.get_all_alerts(days=7)
    except Exception as exc:
        logger.error(f"Error al obtener alertas: {exc}")
        raise HTTPException(status_code=500, detail=f"Error al obtener alertas: {exc}") from exc
