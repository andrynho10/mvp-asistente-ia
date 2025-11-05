"""
Rutas de API para administración de documentos y feedback.
"""
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from config.settings import get_settings
from src.admin import DocumentManager, FeedbackManager
from src.service.schemas import (
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentStatsResponse,
    DocumentUploadResponse,
    FeedbackActionRequest,
    FeedbackCategorizeRequest,
    FeedbackItem,
    FeedbackListResponse,
    FeedbackStatsResponse,
    IngestionStatusResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Router para endpoints de admin
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# Instancias globales
_document_manager: DocumentManager | None = None
_feedback_manager: FeedbackManager | None = None


def get_document_manager() -> DocumentManager:
    """Obtiene la instancia del gestor de documentos."""
    global _document_manager
    if _document_manager is None:
        _document_manager = DocumentManager()
    return _document_manager


def get_feedback_manager() -> FeedbackManager:
    """Obtiene la instancia del gestor de feedback."""
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = FeedbackManager(settings.analytics_db_path)
    return _feedback_manager


# --- Endpoints de Documentos ---


@admin_router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    doc_manager: DocumentManager = Depends(get_document_manager),
) -> DocumentListResponse:
    """
    Lista todos los documentos indexados en el sistema.

    Returns:
        Lista de documentos con metadata
    """
    try:
        documents = doc_manager.list_documents()
        return DocumentListResponse(
            documents=[DocumentInfo(**doc) for doc in documents], total=len(documents)
        )
    except Exception as exc:
        logger.error(f"Error al listar documentos: {exc}")
        raise HTTPException(status_code=500, detail=f"Error al listar documentos: {exc}") from exc


@admin_router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_manager: DocumentManager = Depends(get_document_manager),
) -> DocumentUploadResponse:
    """
    Sube un nuevo documento al sistema.

    Args:
        file: Archivo a subir (.txt, .md, .pdf, .docx, .doc)

    Returns:
        Información del documento subido
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo requerido")

    try:
        # Leer contenido del archivo
        content = await file.read()

        # Agregar documento
        doc_info = doc_manager.add_document(filename=file.filename, content=content)

        logger.info(f"Documento subido exitosamente: {file.filename}")

        return DocumentUploadResponse(**doc_info)
    except ValueError as ve:
        logger.warning(f"Validación fallida al subir documento: {ve}")
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        logger.error(f"Error al subir documento: {exc}")
        raise HTTPException(status_code=500, detail=f"Error al subir documento: {exc}") from exc


@admin_router.delete("/documents/{doc_id}", response_model=DocumentDeleteResponse)
def delete_document(
    doc_id: str,
    doc_manager: DocumentManager = Depends(get_document_manager),
) -> DocumentDeleteResponse:
    """
    Elimina un documento del sistema.

    Args:
        doc_id: ID del documento a eliminar

    Returns:
        Confirmación de eliminación
    """
    try:
        result = doc_manager.delete_document(doc_id)
        logger.info(f"Documento eliminado: {doc_id}")
        return DocumentDeleteResponse(**result)
    except ValueError as ve:
        logger.warning(f"Documento no encontrado: {doc_id}")
        raise HTTPException(status_code=404, detail=str(ve)) from ve
    except Exception as exc:
        logger.error(f"Error al eliminar documento: {exc}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar documento: {exc}") from exc


@admin_router.get("/documents/stats", response_model=DocumentStatsResponse)
def get_document_stats(
    doc_manager: DocumentManager = Depends(get_document_manager),
) -> DocumentStatsResponse:
    """
    Obtiene estadísticas del sistema de documentos.

    Returns:
        Estadísticas de documentos
    """
    try:
        stats = doc_manager.get_stats()
        return DocumentStatsResponse(**stats)
    except Exception as exc:
        logger.error(f"Error al obtener estadísticas: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error al obtener estadísticas: {exc}"
        ) from exc


@admin_router.post("/ingest", response_model=IngestionStatusResponse)
def trigger_ingestion(
    doc_manager: DocumentManager = Depends(get_document_manager),
) -> IngestionStatusResponse:
    """
    Ejecuta el proceso de re-ingesta incremental de documentos.

    Este endpoint procesa todos los documentos activos y actualiza el vector store.

    Returns:
        Estado del proceso de ingesta
    """
    try:
        start_time = time.time()

        # Verificar si hay archivos para ingestar
        files_to_ingest = doc_manager.get_files_for_ingestion()

        if not files_to_ingest:
            return IngestionStatusResponse(
                status="skipped",
                message="No hay documentos pendientes de ingesta",
                documents_processed=0,
            )

        # Importar e inicializar el sistema de ingesta
        from src.knowledge_base.ingest import ingest_from_files

        logger.info(f"Iniciando ingesta de {len(files_to_ingest)} archivos...")

        # Ejecutar ingesta
        ingest_from_files(files_to_ingest, force_reingest=True)

        # Marcar ingesta como completada
        doc_manager.mark_ingestion_complete()

        # Invalidar cache del vector store para forzar recarga
        import src.service.app as app_module
        app_module._cached_vector_store = None

        time_taken = time.time() - start_time

        logger.info(f"Ingesta completada: {len(files_to_ingest)} archivos en {time_taken:.2f}s")

        return IngestionStatusResponse(
            status="completed",
            message=f"Ingesta completada exitosamente",
            documents_processed=len(files_to_ingest),
            time_taken_seconds=round(time_taken, 2),
        )

    except Exception as exc:
        logger.error(f"Error durante la ingesta: {exc}")
        raise HTTPException(status_code=500, detail=f"Error durante la ingesta: {exc}") from exc


# --- Endpoints de Feedback ---


@admin_router.get("/feedback/negative", response_model=FeedbackListResponse)
def get_negative_feedback(
    days: int = 30,
    category: str | None = None,
    status: str | None = None,
    feedback_manager: FeedbackManager = Depends(get_feedback_manager),
) -> FeedbackListResponse:
    """
    Obtiene feedback negativo para revisión.

    Args:
        days: Días hacia atrás a consultar (default: 30)
        category: Filtrar por categoría (missing_info, incorrect_answer, unclear, other)
        status: Filtrar por estado (pending, reviewed, actioned)

    Returns:
        Lista de feedback negativo
    """
    try:
        feedback = feedback_manager.get_negative_feedback(
            days=days, category=category, status=status
        )
        return FeedbackListResponse(
            feedback=[FeedbackItem(**fb) for fb in feedback], total=len(feedback)
        )
    except Exception as exc:
        logger.error(f"Error al obtener feedback negativo: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error al obtener feedback: {exc}"
        ) from exc


@admin_router.put("/feedback/{feedback_id}/categorize")
def categorize_feedback(
    feedback_id: int,
    request: FeedbackCategorizeRequest,
    feedback_manager: FeedbackManager = Depends(get_feedback_manager),
) -> dict[str, str]:
    """
    Categoriza un feedback.

    Args:
        feedback_id: ID del feedback
        request: Categoría (missing_info, incorrect_answer, unclear, other)

    Returns:
        Confirmación
    """
    try:
        feedback_manager.categorize_feedback(feedback_id, request.category)
        return {"status": "categorized", "feedback_id": str(feedback_id)}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        logger.error(f"Error al categorizar feedback: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error al categorizar feedback: {exc}"
        ) from exc


@admin_router.put("/feedback/{feedback_id}/action")
def mark_feedback_actioned(
    feedback_id: int,
    request: FeedbackActionRequest,
    feedback_manager: FeedbackManager = Depends(get_feedback_manager),
) -> dict[str, str]:
    """
    Marca un feedback como accionado.

    Args:
        feedback_id: ID del feedback
        request: Notas sobre la acción tomada

    Returns:
        Confirmación
    """
    try:
        feedback_manager.mark_as_actioned(feedback_id, request.action_notes)
        return {"status": "actioned", "feedback_id": str(feedback_id)}
    except Exception as exc:
        logger.error(f"Error al marcar feedback como accionado: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error al marcar feedback: {exc}"
        ) from exc


@admin_router.get("/feedback/stats", response_model=FeedbackStatsResponse)
def get_feedback_stats(
    days: int = 30,
    feedback_manager: FeedbackManager = Depends(get_feedback_manager),
) -> FeedbackStatsResponse:
    """
    Obtiene estadísticas de feedback.

    Args:
        days: Días hacia atrás a analizar (default: 30)

    Returns:
        Estadísticas de feedback
    """
    try:
        stats = feedback_manager.get_feedback_stats(days=days)
        top_issues = feedback_manager.get_top_issues(days=days, limit=10)
        stats["top_issues"] = top_issues

        return FeedbackStatsResponse(**stats)
    except Exception as exc:
        logger.error(f"Error al obtener estadísticas de feedback: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error al obtener estadísticas: {exc}"
        ) from exc
