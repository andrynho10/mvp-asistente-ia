"""Script para resetear la base de conocimientos y permitir una reingesta desde cero."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Añadir el directorio raíz al path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config.settings import get_settings

settings = get_settings()

print("=" * 70)
print("RESETEAR BASE DE CONOCIMIENTOS")
print("=" * 70)
print("\nEste script eliminará:")
print(f"  1. Vector store (embeddings): {settings.vector_store_path}")
print(f"  2. Documentos procesados: {settings.knowledge_base_path}")
print(f"  3. Feedback: data/feedback/")
print("\nLos documentos RAW en {settings.raw_data_path} NO se eliminarán.")
print("=" * 70)

response = input("\n¿Estás seguro de que quieres continuar? (escribe 'SI' para confirmar): ")

if response.strip().upper() != "SI":
    print("\n❌ Operación cancelada.")
    sys.exit(0)

print("\n🗑️  Eliminando datos...")

# 1. Eliminar vector store
if settings.vector_store_path.exists():
    shutil.rmtree(settings.vector_store_path)
    print(f"  ✓ Vector store eliminado: {settings.vector_store_path}")
else:
    print(f"  ⚠️  Vector store no existe: {settings.vector_store_path}")

# 2. Eliminar archivos procesados
processed_file = settings.knowledge_base_path / "knowledge_chunks.jsonl"
if processed_file.exists():
    processed_file.unlink()
    print(f"  ✓ Archivo procesado eliminado: {processed_file}")
else:
    print(f"  ⚠️  Archivo procesado no existe: {processed_file}")

# 3. Eliminar feedback (opcional)
feedback_dir = Path("data") / "feedback"
if feedback_dir.exists():
    shutil.rmtree(feedback_dir)
    print(f"  ✓ Feedback eliminado: {feedback_dir}")
else:
    print(f"  ⚠️  Feedback no existe: {feedback_dir}")

print("\n" + "=" * 70)
print("✅ RESET COMPLETADO")
print("=" * 70)
print("\nPróximos pasos para reingestar:")
print("\n1. (Opcional) Actualiza los documentos en:", settings.raw_data_path)
print("2. Procesa los documentos con:")
print("   python -m src.knowledge_base.ingest")
print("\n3. Construye el vector store con:")
print("   python -m src.rag_engine.vector_store")
print("\n4. Reinicia el servidor FastAPI")
print("=" * 70)
