"""
Wrapper para ChromaDB con soporte de cifrado transparente.
Proporciona métodos para cifrar/descifrar documentos antes de almacenamiento.

RS4: Cifrado en bases de datos vectoriales
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.security.encryption import EncryptionManager


class ChromaDBCipher:
    """
    Gestor de cifrado para ChromaDB.

    Estrategia:
    - Los embeddings (números) no se cifran (son públicos, derivados de contenido)
    - El contenido (texts) sí se cifra antes de almacenar
    - Los metadatos sensibles se cifran (pero mantenemos algunos sin cifrar para búsqueda)

    Note:
        ChromaDB actualmente no soporta cifrado nativo, así que ciframos el contenido
        antes de agregarlo y lo desciframos al recuperarlo.

    Example:
        cipher = ChromaDBCipher(encryption_manager)

        # Antes de agregar a ChromaDB
        encrypted_texts = cipher.encrypt_texts(texts)
        vector_store.add_texts(encrypted_texts, metadatas)

        # Después de recuperar de ChromaDB
        results = vector_store.similarity_search(query, k=5)
        decrypted = cipher.decrypt_documents(results)
    """

    def __init__(self, encryption_manager: EncryptionManager | None = None):
        """
        Inicializa el cifrador de ChromaDB.

        Args:
            encryption_manager: EncryptionManager para cifrar/descifrar.
                                Si es None, no se cifra (desarrollo).
        """
        self.encryption_manager = encryption_manager
        self.enabled = encryption_manager is not None

    def encrypt_texts(self, texts: List[str]) -> List[str]:
        """
        Cifra lista de textos.

        Args:
            texts: Lista de documentos/chunks

        Returns:
            List[str]: Textos cifrados
        """
        if not self.enabled:
            return texts

        encrypted = []
        for text in texts:
            try:
                enc_text = self.encryption_manager.encrypt(text)
                encrypted.append(enc_text)
            except Exception as e:
                print(f"Error cifrando texto: {e}. Usando original.")
                encrypted.append(text)

        return encrypted

    def decrypt_texts(self, texts: List[str]) -> List[str]:
        """
        Descifra lista de textos.

        Args:
            texts: Lista de textos cifrados

        Returns:
            List[str]: Textos descifrados
        """
        if not self.enabled:
            return texts

        decrypted = []
        for text in texts:
            try:
                dec_text = self.encryption_manager.decrypt(text)
                decrypted.append(dec_text)
            except Exception as e:
                print(f"Error descifrando texto: {e}. Usando original.")
                decrypted.append(text)

        return decrypted

    def encrypt_metadata(
        self,
        metadatas: List[Dict[str, Any]],
        exclude_fields: List[str] | None = None
    ) -> List[Dict[str, Any]]:
        """
        Cifra metadatos sensibles.

        Args:
            metadatas: Lista de dicts de metadatos
            exclude_fields: Campos que NO se deben cifrar (ej: ["source", "process"])
                           para mantener buscabilidad

        Returns:
            List[Dict]: Metadatos con campos sensibles cifrados
        """
        if not self.enabled:
            return metadatas

        exclude_fields = exclude_fields or []
        encrypted_metadatas = []

        for metadata in metadatas:
            encrypted_meta = metadata.copy()

            for key, value in encrypted_meta.items():
                # No cifrar campos específicos (mejora buscabilidad)
                if key in exclude_fields:
                    continue

                # Cifrar campos sensibles
                if key in ["email", "user_id", "author", "owner"]:
                    if value:
                        try:
                            encrypted_meta[key] = self.encryption_manager.encrypt(str(value))
                        except Exception:
                            pass

            encrypted_metadatas.append(encrypted_meta)

        return encrypted_metadatas

    def decrypt_metadata(
        self,
        metadatas: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Descifra metadatos.

        Args:
            metadatas: Lista de metadatos cifrados

        Returns:
            List[Dict]: Metadatos descifrados
        """
        if not self.enabled:
            return metadatas

        decrypted_metadatas = []

        for metadata in metadatas:
            decrypted_meta = metadata.copy()

            for key, value in decrypted_meta.items():
                if key in ["email", "user_id", "author", "owner"]:
                    if value and isinstance(value, str):
                        try:
                            decrypted_meta[key] = self.encryption_manager.decrypt(value)
                        except Exception:
                            pass

            decrypted_metadatas.append(decrypted_meta)

        return decrypted_metadatas

    def encrypt_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Cifra documentos completos (page_content + metadata).

        Args:
            documents: Lista de docs tipo Document de langchain

        Returns:
            List[Dict]: Documentos cifrados
        """
        if not self.enabled:
            return documents

        encrypted_docs = []
        for doc in documents:
            enc_doc = doc.copy() if isinstance(doc, dict) else doc.__dict__.copy()

            # Cifrar contenido
            if "page_content" in enc_doc:
                try:
                    enc_doc["page_content"] = self.encryption_manager.encrypt(
                        enc_doc["page_content"]
                    )
                except Exception:
                    pass

            # Cifrar metadatos sensibles
            if "metadata" in enc_doc and isinstance(enc_doc["metadata"], dict):
                enc_doc["metadata"] = self.encrypt_metadata(
                    [enc_doc["metadata"]],
                    exclude_fields=["source", "process", "document_id"]
                )[0]

            encrypted_docs.append(enc_doc)

        return encrypted_docs

    def decrypt_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Descifra documentos completos.

        Args:
            documents: Lista de documentos cifrados

        Returns:
            List[Dict]: Documentos descifrados
        """
        if not self.enabled:
            return documents

        decrypted_docs = []
        for doc in documents:
            dec_doc = doc.copy() if isinstance(doc, dict) else doc.__dict__.copy()

            # Descifrar contenido
            if "page_content" in dec_doc:
                try:
                    dec_doc["page_content"] = self.encryption_manager.decrypt(
                        dec_doc["page_content"]
                    )
                except Exception:
                    pass

            # Descifrar metadatos
            if "metadata" in dec_doc and isinstance(dec_doc["metadata"], dict):
                dec_doc["metadata"] = self.decrypt_metadata([dec_doc["metadata"]])[0]

            decrypted_docs.append(dec_doc)

        return decrypted_docs

    @staticmethod
    def backup_encrypted_store(
        store_path: Path,
        backup_path: Path,
        encryption_manager: EncryptionManager
    ) -> None:
        """
        Cifra un backup completo del vector store.

        Args:
            store_path: Ruta de la BD original
            backup_path: Ruta del backup cifrado
            encryption_manager: Manager para cifrado
        """
        encryption_manager.encrypt_file(store_path, backup_path)

    @staticmethod
    def restore_encrypted_backup(
        backup_path: Path,
        store_path: Path,
        encryption_manager: EncryptionManager
    ) -> None:
        """
        Restaura un backup cifrado.

        Args:
            backup_path: Ruta del backup cifrado
            store_path: Ruta donde restaurar
            encryption_manager: Manager para descifrado
        """
        encryption_manager.decrypt_file(backup_path, store_path)
