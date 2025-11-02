"""Script de diagnóstico para identificar el error en el servidor."""
from __future__ import annotations

import sys
import io
from pathlib import Path

# Configurar UTF-8 para stdout en Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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
    print(f"   ✓ OLLAMA_BASE_URL: {settings.ollama_base_url}")
    print(f"   ✓ OLLAMA_MODEL: {settings.ollama_model}")
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

# 3. Verificar cliente de Ollama
print("\n3. Verificando conexión con Ollama...")
try:
    import ollama
    from src.rag_engine.pipeline import get_ollama_client

    client_config = get_ollama_client()
    print(f"   ✓ Cliente de Ollama inicializado")
    print(f"   ✓ Modelo configurado: {client_config['model']}")

    # Probar llamada simple
    response = ollama.chat(
        model=client_config['model'],
        messages=[{"role": "user", "content": "Di hola en una palabra"}],
    )
    print(f"   ✓ Llamada a Ollama exitosa: {response['message']['content']}")
except Exception as e:
    print(f"   ✗ Error al conectar con Ollama: {e}")
    import traceback
    traceback.print_exc()
    print("\n   IMPORTANTE: Asegúrate de que:")
    print("   1. Ollama esté instalado y corriendo")
    print("   2. El modelo esté descargado: ollama pull llama3.1:8b-instruct-q4_K_M")
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
