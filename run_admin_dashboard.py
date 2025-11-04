"""
Script para iniciar el dashboard de administración.
"""
import subprocess
import sys
from pathlib import Path

from config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    dashboard_file = Path("src/ui/admin_dashboard.py")

    if not dashboard_file.exists():
        print(f"Error: No se encontró el archivo {dashboard_file}")
        sys.exit(1)

    # Puerto para el admin dashboard (8504 para no conflictuar con otros)
    admin_port = 8504

    print(f"🚀 Iniciando Dashboard de Administración en http://localhost:{admin_port}")
    print("=" * 60)
    print("Panel de Administración del Asistente Organizacional")
    print("=" * 60)
    print()
    print("Funcionalidades:")
    print("  📁 Gestión de documentos (subir, eliminar, listar)")
    print("  💬 Revisión de feedback negativo")
    print("  📊 Estadísticas del sistema")
    print("  🔄 Re-ingesta incremental")
    print()
    print("Presiona Ctrl+C para detener el servidor.")
    print("=" * 60)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(dashboard_file),
            "--server.port",
            str(admin_port),
            "--server.headless",
            "true",
        ]
    )
