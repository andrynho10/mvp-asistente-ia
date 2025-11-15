"""
Utilidades para generar y gestionar certificados SSL/TLS.

RS4: HTTPS + Cifrado en tránsito

Notas importantes:
- Para DESARROLLO: generar certificados auto-firmados (openssl)
- Para PRODUCCIÓN: usar Let's Encrypt + nginx (recomendado)
- NUNCA versionear certificados en Git
"""

import subprocess
from pathlib import Path


def generate_self_signed_cert(
    cert_path: Path,
    key_path: Path,
    days: int = 365,
    country: str = "CL",
    state: str = "Metropolitan",
    city: str = "Santiago",
    organization: str = "Org-Assistant",
    common_name: str = "localhost"
) -> bool:
    """
    Genera un certificado SSL auto-firmado para desarrollo.

    ⚠️ SOLO PARA DESARROLLO - Los navegadores mostrarán advertencia

    Args:
        cert_path: Ruta donde guardar el certificado (.pem)
        key_path: Ruta donde guardar la llave privada (.pem)
        days: Días de validez (default: 1 año)
        country: Código de país (ISO 3166-1 alpha-2)
        state: Estado/Provincia
        city: Ciudad
        organization: Nombre de la organización
        common_name: Nombre común (dominio o localhost)

    Returns:
        bool: True si se generó exitosamente

    Example:
        success = generate_self_signed_cert(
            Path("certs/cert.pem"),
            Path("certs/key.pem"),
            common_name="localhost"
        )
    """
    cert_path.parent.mkdir(parents=True, exist_ok=True)

    # OpenSSL command para generar certificado auto-firmado
    cmd = [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-keyout",
        str(key_path),
        "-out",
        str(cert_path),
        "-days",
        str(days),
        "-nodes",  # Sin contraseña (para producción usar -passout)
        "-subj",
        f"/C={country}/ST={state}/L={city}/O={organization}/CN={common_name}",
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True)
        print(f"✓ Certificado generado: {cert_path}")
        print(f"✓ Llave privada generada: {key_path}")

        # Permisos de seguridad
        key_path.chmod(0o600)
        cert_path.chmod(0o644)

        return True
    except FileNotFoundError:
        print("❌ OpenSSL no encontrado. Instalar con:")
        print("   Windows: choco install openssl")
        print("   Linux: apt install openssl")
        print("   macOS: brew install openssl")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Error generando certificado: {e.stderr.decode()}")
        return False


def verify_certificate(cert_path: Path) -> bool:
    """
    Verifica que un certificado es válido.

    Args:
        cert_path: Ruta al certificado

    Returns:
        bool: True si es válido
    """
    if not cert_path.exists():
        return False

    cmd = ["openssl", "x509", "-in", str(cert_path), "-text", "-noout"]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception:
        return False


def get_certificate_info(cert_path: Path) -> dict:
    """
    Extrae información del certificado.

    Args:
        cert_path: Ruta al certificado

    Returns:
        dict: Información del certificado (CN, válido desde, válido hasta, etc.)
    """
    import re
    from datetime import datetime

    if not cert_path.exists():
        return {}

    cmd = ["openssl", "x509", "-in", str(cert_path), "-text", "-noout"]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        text = result.stdout

        info = {}

        # Extraer CN (Common Name)
        cn_match = re.search(r"Subject:.*CN\s*=\s*([^,\n]+)", text)
        if cn_match:
            info["common_name"] = cn_match.group(1)

        # Extraer fechas
        valid_from = re.search(r"Not Before:\s*(.+)", text)
        if valid_from:
            info["valid_from"] = valid_from.group(1)

        valid_to = re.search(r"Not After\s*:\s*(.+)", text)
        if valid_to:
            info["valid_to"] = valid_to.group(1)

        return info
    except Exception:
        return {}


class SSLConfig:
    """
    Configuración de SSL/TLS para FastAPI.

    Maneja tanto desarrollo (auto-firmado) como producción.
    """

    def __init__(
        self,
        enabled: bool = False,
        cert_path: Path | None = None,
        key_path: Path | None = None,
        auto_generate: bool = True
    ):
        """
        Inicializa configuración SSL.

        Args:
            enabled: Activar HTTPS
            cert_path: Ruta al certificado
            key_path: Ruta a la llave privada
            auto_generate: Generar certificado auto-firmado si falta (solo dev)
        """
        self.enabled = enabled
        self.cert_path = cert_path
        self.key_path = key_path
        self.auto_generate = auto_generate

    def is_ready(self) -> bool:
        """Verifica que los certificados existan y sean válidos."""
        if not self.enabled:
            return False

        if not self.cert_path or not self.key_path:
            return False

        if not self.cert_path.exists() or not self.key_path.exists():
            if self.auto_generate:
                print("Certificados no encontrados. Generando auto-firmados...")
                return generate_self_signed_cert(self.cert_path, self.key_path)
            return False

        return verify_certificate(self.cert_path)

    def get_uvicorn_config(self) -> dict:
        """
        Retorna configuración para uvicorn con SSL.

        Returns:
            dict: Config con ssl_certfile, ssl_keyfile (si está habilitado)
        """
        if not self.is_ready():
            return {}

        return {
            "ssl_certfile": str(self.cert_path),
            "ssl_keyfile": str(self.key_path),
        }
