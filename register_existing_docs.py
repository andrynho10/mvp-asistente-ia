"""
Script para registrar documentos existentes en el sistema de metadata del admin.

Este script escanea data/raw/ y crea entradas en metadata.json para documentos
que ya existían antes de implementar el panel de administración.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from config.settings import get_settings


def calculate_file_hash(file_path: Path) -> str:
    """Calcula hash MD5 de un archivo."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def register_existing_documents():
    """Registra documentos existentes en metadata.json"""
    settings = get_settings()
    raw_data_path = settings.raw_data_path
    metadata_path = raw_data_path / "metadata.json"

    # Extensiones soportadas
    supported_extensions = [".txt", ".md", ".pdf", ".docx", ".doc"]

    # Inicializar metadata
    metadata = {
        "documents": {},
        "last_updated": datetime.now().isoformat(),
    }

    # Buscar todos los archivos en data/raw/
    files_found = []
    for file_path in raw_data_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            # Ignorar archivos de metadata
            if file_path.name == "metadata.json":
                continue
            files_found.append(file_path)

    print(f"Encontrados {len(files_found)} documentos en {raw_data_path}")

    # Registrar cada documento
    for file_path in files_found:
        # Generar ID único
        doc_id = hashlib.md5(f"{file_path.name}_{file_path.stat().st_mtime}".encode()).hexdigest()[:12]

        # Calcular hash del contenido
        file_hash = calculate_file_hash(file_path)

        # Información del documento
        doc_info = {
            "filename": file_path.name,
            "file_path": str(file_path),
            "size_bytes": file_path.stat().st_size,
            "uploaded_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            "file_hash": file_hash,
            "status": "active",
        }

        metadata["documents"][doc_id] = doc_info
        print(f"  [OK] Registrado: {file_path.name} (ID: {doc_id})")

    # Guardar metadata
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Metadata guardada en: {metadata_path}")
    print(f"Total documentos registrados: {len(metadata['documents'])}")
    print("\nAhora puedes ver los documentos en el Panel de Administracion (http://localhost:8504)")


if __name__ == "__main__":
    print("=" * 70)
    print("Registro de Documentos Existentes")
    print("=" * 70)
    print()

    try:
        register_existing_documents()
        print("\n" + "=" * 70)
        print("Proceso completado exitosamente")
        print("=" * 70)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
