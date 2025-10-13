"""Script completo para reingestar documentos y reconstruir el vector store."""
from __future__ import annotations

import sys
from pathlib import Path

# Añadir el directorio raíz al path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config.settings import get_settings
from src.knowledge_base.ingest import run_ingestion
from src.rag_engine.vector_store import build_vector_store

settings = get_settings()

print("=" * 70)
print("REINGESTA COMPLETA DE DOCUMENTOS")
print("=" * 70)
print(f"\n📂 Carpeta de documentos RAW: {settings.raw_data_path}")
print(f"📝 Carpeta de procesados: {settings.knowledge_base_path}")
print(f"🗄️  Vector store: {settings.vector_store_path}")
print("\nEste script realizará:")
print("  1. Procesar documentos de la carpeta RAW")
print("  2. Extraer keywords con TF-IDF")
print("  3. Crear chunks de texto")
print("  4. Generar embeddings con sentence-transformers")
print("  5. Construir/actualizar el vector store con ChromaDB")
print("\n⏱️  Esto puede tomar varios minutos dependiendo del tamaño de los documentos.")
print("=" * 70)

response = input("\n¿Continuar con la reingesta? (escribe 'SI' para confirmar): ")

if response.strip().upper() != "SI":
    print("\n❌ Operación cancelada.")
    sys.exit(0)

print("\n" + "=" * 70)
print("PASO 1: PROCESANDO DOCUMENTOS")
print("=" * 70)

try:
    output_file = run_ingestion()
    print(f"✅ Documentos procesados exitosamente: {output_file}")
except Exception as e:
    print(f"\n❌ Error al procesar documentos: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("PASO 2: CONSTRUYENDO VECTOR STORE")
print("=" * 70)
print("⏳ Generando embeddings (esto puede tomar tiempo)...")

try:
    vector_store = build_vector_store()
    print(f"✅ Vector store construido exitosamente: {settings.vector_store_path}")
except Exception as e:
    print(f"\n❌ Error al construir vector store: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ REINGESTA COMPLETADA EXITOSAMENTE")
print("=" * 70)
print("\n📊 Estadísticas:")
print(f"  - Documentos procesados: {output_file}")
print(f"  - Vector store: {settings.vector_store_path}")
print("\n🚀 Próximos pasos:")
print("  1. Reinicia el servidor FastAPI (Ctrl+C y vuelve a ejecutar)")
print("  2. Prueba el sistema desde Streamlit")
print("=" * 70)
