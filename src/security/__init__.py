"""
Módulo de seguridad para cifrado de datos en reposo.
Implementa RS4 del proyecto.
"""

from src.security.encryption import (
    EncryptionManager,
    generate_encryption_key,
    load_or_create_encryption_key,
)

__all__ = [
    "EncryptionManager",
    "generate_encryption_key",
    "load_or_create_encryption_key",
]
