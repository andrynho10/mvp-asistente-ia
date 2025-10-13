from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

from groq import Groq
from langchain.schema import Document
from langchain_community.vectorstores import Chroma

from config.settings import get_settings

SYSTEM_PROMPT = (
    "Eres un asistente corporativo especializado en procedimientos internos. "
    "Responde con precisión, indica pasos clave y menciona responsables cuando estén disponibles. "
    "Si no existe información suficiente, indícalo y sugiere con qué área validar la respuesta."
)


@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("Falta GROQ_API_KEY en el entorno.")
    return Groq(api_key=settings.groq_api_key)


def render_context(documents: List[Document]) -> str:
    rendered = []
    for doc in documents:
        metadata = doc.metadata or {}
        source = metadata.get("source", "desconocido")
        rendered.append(f"[{source}] {doc.page_content}")
    return "\n".join(rendered)


def build_messages(question: str, context: str) -> List[Dict[str, str]]:
    user_prompt = (
        "Pregunta del colaborador:\n"
        f"{question}\n\n"
        "Información recuperada:\n"
        f"{context}\n\n"
        "Elabora una respuesta estructurada con pasos claros, responsables involucrados y enlaces a la "
        "fuente cuando exista. Si alguna parte falta, indícalo explícitamente."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def call_groq(messages: List[Dict[str, str]], temperature: float = 0.2) -> Dict[str, Any]:
    settings = get_settings()
    client = get_groq_client()
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=temperature,
    )
    if not response.choices:
        raise RuntimeError("La respuesta de Groq no contiene resultados.")
    return response.model_dump()


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
) -> Dict[str, Any]:
    documents = retrieve_documents(vector_store, question, metadata_filters, top_k=top_k)
    context = render_context(documents)
    messages = build_messages(question, context)
    raw_response = call_groq(messages)
    content = raw_response["choices"][0]["message"]["content"].strip()
    return {
        "answer": content,
        "source_documents": documents,
        "context_rendered": context,
        "raw_response": raw_response,
    }
