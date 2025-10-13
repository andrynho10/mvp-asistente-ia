"""Script de diagnóstico para identificar el error en el servidor."""
from __future__ import annotations

import sys
from pathlib import Path

# Añadir el directorio raíz al path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

print("=" * 60)
print("DIAGNÓSTICO DEL SISTEMA")
print("=" * 60)

# 1. Verificar configuración
print("\n1. Verificando configuración...")
try:
    from config.settings import get_settings
    settings = get_settings()
    print(f"   ✓ GROQ_API_KEY: {'***' + settings.groq_api_key[-8:] if settings.groq_api_key else 'NO CONFIGURADA'}")
    print(f"   ✓ GROQ_MODEL: {settings.groq_model}")
    print(f"   ✓ VECTOR_STORE_PATH: {settings.vector_store_path}")
    print(f"   ✓ Vector store existe: {settings.vector_store_path.exists()}")
except Exception as e:
    print(f"   ✗ Error al cargar configuración: {e}")
    sys.exit(1)

# 2. Verificar vector store
print("\n2. Verificando vector store...")
try:
    from src.rag_engine import load_vector_store
    vector_store = load_vector_store()
    print(f"   ✓ Vector store cargado exitosamente")

    # Probar búsqueda
    results = vector_store.similarity_search("test", k=1)
    print(f"   ✓ Búsqueda funciona (encontró {len(results)} documentos)")
except Exception as e:
    print(f"   ✗ Error al cargar vector store: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Verificar cliente de Groq
print("\n3. Verificando conexión con Groq...")
try:
    from src.rag_engine.pipeline import get_groq_client
    client = get_groq_client()
    print(f"   ✓ Cliente de Groq inicializado")

    # Probar llamada simple
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": "Di hola"}],
        max_tokens=10
    )
    print(f"   ✓ Llamada a Groq exitosa: {response.choices[0].message.content}")
except Exception as e:
    print(f"   ✗ Error al conectar con Groq: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Probar pipeline completo
print("\n4. Probando pipeline completo (ask_question)...")
try:
    from src.rag_engine import ask_question
    result = ask_question(
        vector_store=vector_store,
        question="¿Cómo solicito un reembolso?",
        top_k=2
    )
    print(f"   ✓ Pipeline funciona correctamente")
    print(f"   ✓ Respuesta generada: {result['answer'][:100]}...")
except Exception as e:
    print(f"   ✗ Error en pipeline: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ TODOS LOS TESTS PASARON - El sistema debería funcionar")
print("=" * 60)
print("\nSi Streamlit sigue dando error, el problema está en:")
print("1. El servidor FastAPI no está corriendo")
print("2. El servidor está en un puerto diferente")
print("3. Necesitas reiniciar el servidor después de los cambios")
