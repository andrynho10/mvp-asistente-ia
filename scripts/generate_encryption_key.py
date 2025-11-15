#!/usr/bin/env python3
"""
Script para generar claves de cifrado Fernet para la aplicación.

Uso:
    python scripts/generate_encryption_key.py

Output:
    - Imprime la llave Fernet
    - Opcionalmente guarda en .env
    - Muestra instrucciones de seguridad
"""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cryptography.fernet import Fernet


def generate_and_display_key():
    """Genera y muestra la llave de cifrado."""
    key = Fernet.generate_key().decode("utf-8")

    print("\n" + "=" * 80)
    print("🔐 GENERADOR DE CLAVES DE CIFRADO - Org-Assistant")
    print("=" * 80)
    print()
    print("✓ Llave Fernet generada (256-bit AES):")
    print()
    print(f"  {key}")
    print()
    print("=" * 80)
    print()
    print("📋 INSTRUCCIONES DE USO:")
    print()
    print("1. DESARROLLO:")
    print("   - Copiar la llave arriba")
    print("   - Abrir .env.local (crear si no existe)")
    print("   - Agregar: ENCRYPTION_KEY=<llave>")
    print()
    print("2. PRODUCCIÓN (⚠️ CRÍTICO):")
    print("   - NO versionar la llave en Git")
    print("   - Guardar en:")
    print("     • Variables de entorno del servidor")
    print("     • Sistema de secretos (AWS Secrets Manager, HashiCorp Vault, etc.)")
    print("     • Archivo protegido con permisos 0600")
    print("   - Rotar periódicamente (cada 90 días)")
    print("   - Mantener backup cifrado")
    print()
    print("3. PÉRDIDA DE LLAVE:")
    print("   ❌ Sin la llave, los datos cifrados NO pueden recuperarse")
    print("   ✓ Guardar en lugar seguro (password manager, vault, etc.)")
    print()
    print("=" * 80)
    print()

    # Preguntar si guardar en .env
    response = input("¿Guardar en .env.local? (s/n): ").strip().lower()
    if response in ["s", "si", "yes", "y"]:
        env_local = Path(".env.local")
        content = f"ENCRYPTION_KEY={key}\n"

        if env_local.exists():
            # Preguntar si sobreescribir
            if input("  .env.local ya existe. ¿Sobreescribir? (s/n): ").strip().lower() in ["s", "si"]:
                env_local.write_text(content)
                print(f"  ✓ Guardado en {env_local}")
        else:
            env_local.write_text(content)
            print(f"  ✓ Guardado en {env_local}")

            # Proteger permisos
            try:
                env_local.chmod(0o600)
                print(f"  ✓ Permisos establecidos a 0600 (solo lectura propietario)")
            except Exception:
                print(f"  ⚠️  No se pudieron cambiar permisos (Windows no lo requiere)")

    print()


if __name__ == "__main__":
    generate_and_display_key()
