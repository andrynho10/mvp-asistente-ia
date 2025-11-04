"""
Script para lanzar el dashboard de analytics.
"""

import os
import sys

from config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()

    # Configurar puerto (usar variable de entorno o default)
    analytics_port = os.environ.get("ANALYTICS_PORT", "8502")

    print(f"🚀 Iniciando Analytics Dashboard en puerto {analytics_port}...")
    print(f"📊 Dashboard disponible en: http://localhost:{analytics_port}")
    print(f"🗄️  Base de datos: {settings.analytics_db_path}")

    os.system(
        f'streamlit run src/ui/analytics_dashboard.py --server.port {analytics_port} --server.headless true'
    )
