from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

import ollama
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

from config.settings import get_settings
from src.memory import ConversationMemory

SYSTEM_PROMPT = (
    "Eres un asistente corporativo especializado en procedimientos internos. "
    "IMPORTANTE: Debes responder ÚNICAMENTE basándote en la información proporcionada en el contexto. "
    "NO inventes información ni des respuestas genéricas. "
    "Si la información recuperada no es suficiente para responder la pregunta, indícalo claramente y "
    "sugiere con qué área validar la respuesta. "
    "Responde con precisión, indica pasos clave y menciona responsables cuando estén disponibles."
)


@lru_cache(maxsize=1)
def get_ollama_client():
    """Verifica que Ollama esté disponible y el modelo esté descargado."""
    settings = get_settings()
    try:
        # Verificar que Ollama esté corriendo
        ollama.list()
        return {"base_url": settings.ollama_base_url, "model": settings.ollama_model}
    except Exception as e:
        raise RuntimeError(
            f"No se puede conectar con Ollama. Asegúrate de que Ollama esté corriendo. Error: {e}"
        )


def render_context(documents: List[Document]) -> str:
    rendered = []
    for doc in documents:
        metadata = doc.metadata or {}
        source = metadata.get("source", "desconocido")
        rendered.append(f"[{source}] {doc.page_content}")
    return "\n".join(rendered)


def build_messages(
    question: str, context: str, conversation_memory: Optional[ConversationMemory] = None
) -> List[Dict[str, str]]:
    """
    Construye los mensajes para el LLM, opcionalmente incluyendo historial conversacional.

    Args:
        question: Pregunta actual del usuario
        context: Contexto recuperado del vector store
        conversation_memory: Memoria conversacional (opcional)

    Returns:
        Lista de mensajes formateados para el LLM
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Agregar historial si existe
    if conversation_memory and conversation_memory.messages:
        # Incluir el historial completo en el prompt
        history_context = conversation_memory.get_context_string()
        user_prompt = (
            f"{history_context}\n\n"
            "---\n\n"
            "Pregunta actual del colaborador:\n"
            f"{question}\n\n"
            "Información recuperada de la base de conocimientos:\n"
            f"{context}\n\n"
            "Instrucciones:\n"
            "- Ten en cuenta el historial de la conversación para dar contexto a tu respuesta\n"
            "- Si el usuario hace referencia a algo anterior, usa el historial\n"
            "- Responde SOLO con la información del contexto y el historial\n"
            "- Si el contexto está vacío o no responde la pregunta, indícalo claramente\n"
            "- NO uses conocimiento general, solo usa lo que está en el contexto\n"
            "- Elabora una respuesta estructurada con pasos claros y responsables involucrados\n"
            "- Menciona las fuentes cuando estén disponibles"
        )
    else:
        # Sin historial (primera pregunta o sin memoria)
        user_prompt = (
            "Pregunta del colaborador:\n"
            f"{question}\n\n"
            "Información recuperada de la base de conocimientos:\n"
            f"{context}\n\n"
            "Instrucciones:\n"
            "- Responde SOLO con la información del contexto anterior\n"
            "- Si el contexto está vacío o no responde la pregunta, indícalo claramente\n"
            "- NO uses conocimiento general, solo usa lo que está en el contexto\n"
            "- Elabora una respuesta estructurada con pasos claros y responsables involucrados\n"
            "- Menciona las fuentes cuando estén disponibles"
        )

    messages.append({"role": "user", "content": user_prompt})
    return messages


def call_local_llm(messages: List[Dict[str, str]], temperature: float = 0.2) -> Dict[str, Any]:
    """Llama al modelo local de Ollama para generar una respuesta."""
    client_config = get_ollama_client()

    try:
        response = ollama.chat(
            model=client_config["model"],
            messages=messages,
            options={
                "temperature": temperature,
            }
        )

        # Validar que la respuesta tenga el formato esperado
        if not response or "message" not in response:
            raise RuntimeError("La respuesta de Ollama no contiene el campo 'message'.")

        # Adaptar la respuesta al formato compatible con el código existente
        return {
            "choices": [{
                "message": {
                    "role": response["message"]["role"],
                    "content": response["message"]["content"]
                }
            }],
            "model": response.get("model", client_config["model"]),
            "created_at": response.get("created_at", ""),
        }
    except Exception as e:
        raise RuntimeError(f"Error al llamar a Ollama: {e}")


def retrieve_documents(
    vector_store: Chroma,
    question: str,
    metadata_filters: Optional[Dict[str, Any]] = None,
    top_k: int = 4,
) -> List[Document]:
    return vector_store.similarity_search(question, k=top_k, filter=metadata_filters)


def ask_question(
    vector_store: Chroma,
    question: str,
    metadata_filters: Optional[Dict[str, Any]] = None,
    top_k: int = 4,
    conversation_memory: Optional[ConversationMemory] = None,
) -> Dict[str, Any]:
    """
    Responde una pregunta usando RAG, opcionalmente con memoria conversacional.

    Args:
        vector_store: Vector store con documentos indexados
        question: Pregunta del usuario
        metadata_filters: Filtros opcionales de metadata
        top_k: Número de documentos a recuperar
        conversation_memory: Memoria conversacional (opcional)

    Returns:
        Dict con answer, source_documents, context_rendered, raw_response
    """
    documents = retrieve_documents(vector_store, question, metadata_filters, top_k=top_k)
    context = render_context(documents)
    messages = build_messages(question, context, conversation_memory)
    raw_response = call_local_llm(messages)
    content = raw_response["choices"][0]["message"]["content"].strip()

    # Actualizar memoria si se proporciona
    if conversation_memory:
        conversation_memory.add_exchange(question, content)

    return {
        "answer": content,
        "source_documents": documents,
        "context_rendered": context,
        "raw_response": raw_response,
    }
