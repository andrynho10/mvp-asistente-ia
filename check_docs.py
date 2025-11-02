"""Script para verificar si hay documentos en el vector store."""
from src.rag_engine import load_vector_store

print("Cargando vector store...")
vs = load_vector_store()

print("\nBuscando documentos...")
docs = vs.similarity_search('procedimiento', k=3)

print(f"\n✓ Documentos encontrados: {len(docs)}")

if docs:
    print("\n--- Primeros 3 documentos ---")
    for i, doc in enumerate(docs[:3], 1):
        print(f"\nDocumento {i}:")
        print(f"  Fuente: {doc.metadata.get('source', 'desconocido')}")
        print(f"  Contenido: {doc.page_content[:150]}...")
else:
    print("\n⚠️ NO HAY DOCUMENTOS EN EL VECTOR STORE")
    print("Ejecuta: python reingest.py")
