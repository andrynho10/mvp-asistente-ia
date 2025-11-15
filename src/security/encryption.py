"""
Gestor de cifrado Fernet para datos sensibles en reposo.
Utiliza cryptography.fernet para cifrado simétrico de alto rendimiento.

RS4: Cifrado HTTPS + en reposo
"""

import base64
import json
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet


def generate_encryption_key() -> str:
    """
    Genera una nueva llave de cifrado Fernet.

    Returns:
        str: Llave Fernet en formato string (puede guardarse en .env)

    Usage:
        key = generate_encryption_key()
        # Guardar en .env: ENCRYPTION_KEY=<key>
    """
    key = Fernet.generate_key()
    return key.decode("utf-8")


def load_or_create_encryption_key(
    key_path: Path,
    override_env_key: str | None = None
) -> str:
    """
    Carga una llave de cifrado desde archivo o la crea si no existe.

    Args:
        key_path: Ruta donde guardar/cargar la llave
        override_env_key: Si se proporciona una llave desde .env, usarla en lugar de cargar del archivo

    Returns:
        str: Llave Fernet

    Raises:
        ValueError: Si la llave de .env es inválida
    """
    # Prioridad: variable de entorno > archivo > generar nueva
    if override_env_key:
        # Validar que es una llave Fernet válida
        try:
            Fernet(override_env_key.encode())
            return override_env_key
        except Exception as e:
            raise ValueError(f"ENCRYPTION_KEY inválida en .env: {e}")

    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()

    # Generar nueva y guardar
    key_path.parent.mkdir(parents=True, exist_ok=True)
    new_key = generate_encryption_key()
    key_path.write_text(new_key, encoding="utf-8")
    key_path.chmod(0o600)  # Solo lectura para propietario (Linux/Mac)

    return new_key


class EncryptionManager:
    """
    Gestor centralizado de cifrado Fernet.

    Responsabilidades:
    - Cifrado/descifrado de strings y bytes
    - Manejo seguro de claves
    - Cifrado de archivos JSON
    - Integración con SQLite y ChromaDB

    Example:
        manager = EncryptionManager(encryption_key="...")
        encrypted = manager.encrypt("datos sensibles")
        decrypted = manager.decrypt(encrypted)
    """

    def __init__(self, encryption_key: str):
        """
        Inicializa el manager con una llave de cifrado.

        Args:
            encryption_key: Llave Fernet válida (base64)

        Raises:
            ValueError: Si la llave es inválida
        """
        try:
            self.cipher = Fernet(encryption_key.encode())
            self._key = encryption_key
        except Exception as e:
            raise ValueError(f"Llave de cifrado inválida: {e}")

    def encrypt(self, data: str | bytes) -> str:
        """
        Cifra un string o bytes.

        Args:
            data: Datos a cifrar

        Returns:
            str: Datos cifrados en base64
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        encrypted = self.cipher.encrypt(data)
        return encrypted.decode("utf-8")

    def decrypt(self, encrypted_data: str) -> str:
        """
        Descifra datos.

        Args:
            encrypted_data: Datos cifrados (desde encrypt())

        Returns:
            str: Datos descifrados

        Raises:
            cryptography.fernet.InvalidToken: Si los datos están corrupto o llave es incorrecta
        """
        encrypted_bytes = encrypted_data.encode("utf-8")
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted.decode("utf-8")

    def encrypt_json(self, data: Dict[str, Any]) -> str:
        """
        Cifra un diccionario JSON.

        Args:
            data: Diccionario a cifrar

        Returns:
            str: JSON cifrado en base64
        """
        json_str = json.dumps(data, ensure_ascii=False)
        return self.encrypt(json_str)

    def decrypt_json(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Descifra un JSON.

        Args:
            encrypted_data: JSON cifrado

        Returns:
            Dict: Diccionario descifrado
        """
        json_str = self.decrypt(encrypted_data)
        return json.loads(json_str)

    def encrypt_file(self, input_path: Path, output_path: Path) -> None:
        """
        Cifra un archivo completo.

        Args:
            input_path: Archivo original
            output_path: Archivo cifrado
        """
        data = input_path.read_bytes()
        encrypted = self.cipher.encrypt(data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(encrypted)

    def decrypt_file(self, input_path: Path, output_path: Path) -> None:
        """
        Descifra un archivo.

        Args:
            input_path: Archivo cifrado
            output_path: Archivo descifrado
        """
        encrypted_data = input_path.read_bytes()
        decrypted = self.cipher.decrypt(encrypted_data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(decrypted)

    @staticmethod
    def is_encrypted(data: str) -> bool:
        """
        Verifica si un string está cifrado (heurística).

        Args:
            data: Datos a verificar

        Returns:
            bool: True si parece ser Fernet cifrado
        """
        try:
            # Fernet tokens son base64 válido y contienen timestamp
            if not isinstance(data, str) or len(data) < 50:
                return False
            base64.urlsafe_b64decode(data)
            return data.startswith("gAAAAAB")  # Fernet magic prefix
        except Exception:
            return False
