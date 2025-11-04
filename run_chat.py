"""
Script para lanzar la interfaz de chat con memoria conversacional.
"""

import os
import sys

from config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()

    # Configurar puerto (usar variable de entorno o default)
    chat_port = os.environ.get("CHAT_PORT", "8503")

    print(f"🚀 Iniciando Chat con Memoria Conversacional en puerto {chat_port}...")
    print(f"💬 Chat disponible en: http://localhost:{chat_port}")
    print(f"📝 Sesiones se almacenan en: {settings.sessions_db_path}")

    os.system(
        f'streamlit run src/ui/chat_app.py --server.port {chat_port} --server.headless true'
    )
