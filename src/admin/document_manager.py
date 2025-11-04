"""
Gestor de documentos para operaciones CRUD y re-ingesta incremental.
"""
import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


class DocumentManager:
    """Gestor de documentos con soporte para re-ingesta incremental."""

    def __init__(self):
        self.settings = get_settings()
        self.raw_data_path = self.settings.raw_data_path
        self.processed_path = self.settings.knowledge_base_path
        self.metadata_path = self.raw_data_path / "metadata.json"

        # Crear directorios si no existen
        self.raw_data_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)

        # Cargar o inicializar metadata
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> dict[str, Any]:
        """Carga metadata de documentos indexados."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error al cargar metadata: {e}")
                return {"documents": {}, "last_updated": datetime.now().isoformat()}
        return {"documents": {}, "last_updated": datetime.now().isoformat()}

    def _save_metadata(self) -> None:
        """Guarda metadata de documentos."""
        self.metadata["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar metadata: {e}")

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calcula hash MD5 de un archivo."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def list_documents(self) -> list[dict[str, Any]]:
        """
        Lista todos los documentos indexados.

        Returns:
            Lista de documentos con metadata
        """
        documents = []
        for doc_id, doc_info in self.metadata.get("documents", {}).items():
            documents.append(
                {
                    "id": doc_id,
                    "filename": doc_info.get("filename"),
                    "size_bytes": doc_info.get("size_bytes"),
                    "uploaded_at": doc_info.get("uploaded_at"),
                    "file_hash": doc_info.get("file_hash"),
                    "status": doc_info.get("status", "active"),
                }
            )
        return documents

    def get_document(self, doc_id: str) -> Optional[dict[str, Any]]:
        """
        Obtiene información de un documento específico.

        Args:
            doc_id: ID del documento

        Returns:
            Información del documento o None si no existe
        """
        return self.metadata.get("documents", {}).get(doc_id)

    def add_document(self, filename: str, content: bytes) -> dict[str, Any]:
        """
        Agrega un nuevo documento al sistema.

        Args:
            filename: Nombre del archivo
            content: Contenido del archivo en bytes

        Returns:
            Información del documento agregado

        Raises:
            ValueError: Si el tipo de archivo no es soportado
        """
        # Validar extensión
        supported_extensions = [".txt", ".md", ".pdf", ".docx", ".doc"]
        file_ext = Path(filename).suffix.lower()
        if file_ext not in supported_extensions:
            raise ValueError(
                f"Tipo de archivo no soportado: {file_ext}. "
                f"Extensiones soportadas: {', '.join(supported_extensions)}"
            )

        # Generar ID único basado en filename y timestamp
        timestamp = datetime.now().isoformat()
        doc_id = hashlib.md5(f"{filename}_{timestamp}".encode()).hexdigest()[:12]

        # Guardar archivo
        file_path = self.raw_data_path / f"{doc_id}_{filename}"
        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Error al guardar archivo: {e}")
            raise ValueError(f"Error al guardar archivo: {e}")

        # Calcular hash
        file_hash = self._calculate_file_hash(file_path)

        # Verificar si ya existe un documento con el mismo hash
        for existing_id, existing_doc in self.metadata.get("documents", {}).items():
            if existing_doc.get("file_hash") == file_hash and existing_doc.get("status") == "active":
                logger.warning(f"Documento duplicado detectado: {filename}")
                # Eliminar archivo recién subido
                file_path.unlink()
                raise ValueError(
                    f"Este documento ya existe en el sistema (ID: {existing_id}). "
                    "No se permiten duplicados."
                )

        # Guardar metadata
        doc_info = {
            "filename": filename,
            "file_path": str(file_path),
            "size_bytes": len(content),
            "uploaded_at": timestamp,
            "file_hash": file_hash,
            "status": "active",
        }

        self.metadata.setdefault("documents", {})[doc_id] = doc_info
        self._save_metadata()

        logger.info(f"Documento agregado: {doc_id} - {filename}")

        return {"id": doc_id, **doc_info}

    def delete_document(self, doc_id: str) -> dict[str, str]:
        """
        Elimina un documento del sistema.

        Args:
            doc_id: ID del documento a eliminar

        Returns:
            Mensaje de confirmación

        Raises:
            ValueError: Si el documento no existe
        """
        doc_info = self.metadata.get("documents", {}).get(doc_id)
        if not doc_info:
            raise ValueError(f"Documento no encontrado: {doc_id}")

        # Eliminar archivo físico
        file_path = Path(doc_info["file_path"])
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Archivo eliminado: {file_path}")
        except Exception as e:
            logger.error(f"Error al eliminar archivo físico: {e}")

        # Marcar como eliminado en metadata (soft delete)
        self.metadata["documents"][doc_id]["status"] = "deleted"
        self.metadata["documents"][doc_id]["deleted_at"] = datetime.now().isoformat()
        self._save_metadata()

        logger.info(f"Documento eliminado: {doc_id}")

        return {"status": "deleted", "doc_id": doc_id, "filename": doc_info["filename"]}

    def needs_reingestion(self) -> bool:
        """
        Verifica si hay documentos que necesitan ser re-ingestados.

        Returns:
            True si hay cambios pendientes
        """
        # Verificar si hay documentos nuevos o eliminados
        for doc_info in self.metadata.get("documents", {}).values():
            if doc_info.get("status") in ["active", "deleted"]:
                # Verificar si el documento está en el vector store
                # Por simplicidad, asumimos que si hay documentos activos/eliminados
                # y la metadata cambió, necesita re-ingesta
                return True
        return False

    def get_files_for_ingestion(self) -> list[Path]:
        """
        Obtiene la lista de archivos que deben ser ingestados.

        Returns:
            Lista de rutas de archivos activos
        """
        files = []
        for doc_info in self.metadata.get("documents", {}).values():
            if doc_info.get("status") == "active":
                file_path = Path(doc_info["file_path"])
                if file_path.exists():
                    files.append(file_path)
        return files

    def mark_ingestion_complete(self) -> None:
        """Marca que la ingesta ha sido completada."""
        self.metadata["last_ingestion"] = datetime.now().isoformat()
        self._save_metadata()
        logger.info("Ingesta completada y registrada")

    def get_stats(self) -> dict[str, Any]:
        """
        Obtiene estadísticas del sistema de documentos.

        Returns:
            Estadísticas de documentos
        """
        docs = self.metadata.get("documents", {})
        active_docs = [d for d in docs.values() if d.get("status") == "active"]
        deleted_docs = [d for d in docs.values() if d.get("status") == "deleted"]

        total_size = sum(d.get("size_bytes", 0) for d in active_docs)

        return {
            "total_documents": len(active_docs),
            "deleted_documents": len(deleted_docs),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "last_updated": self.metadata.get("last_updated"),
            "last_ingestion": self.metadata.get("last_ingestion"),
        }
