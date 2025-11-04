# 🤖 Asistente Organizacional - MVP

Prototipo basado en **RAG (Retrieval Augmented Generation)** para apoyar la capacitación e inducción de colaboradores, brindando acceso inteligente a procedimientos críticos, políticas y resoluciones históricas.

**Stack tecnológico:**
- 🧠 LLM: Ollama (llama3.1:8b-instruct local)
- 📚 Vector Store: ChromaDB
- 🔍 Embeddings: Sentence Transformers
- ⚡ API: FastAPI
- 🎨 UI: Streamlit
- 📊 Analytics: SQLite + Plotly
- 💬 Memoria Conversacional: SQLite con gestión de sesiones
- 🐍 Python 3.10+

---

## 📁 Estructura del Proyecto

```
org-assistant/
├── config/              # Configuración (settings.py, .env)
├── data/
│   ├── raw/            # 📂 Documentos originales (.txt, .pdf, .docx, etc.)
│   ├── processed/      # 📝 Chunks procesados (generado automáticamente)
│   ├── embeddings/     # 🗄️ Vector store ChromaDB (generado automáticamente)
│   ├── analytics/      # 📊 Base de datos de métricas (generado automáticamente)
│   ├── sessions/       # 💬 Sesiones conversacionales (generado automáticamente)
│   └── feedback/       # 📝 Feedback de usuarios (generado automáticamente)
├── src/
│   ├── knowledge_base/ # Pipeline de ingesta y procesamiento
│   ├── rag_engine/     # Lógica RAG (retrieval + generación)
│   ├── service/        # API FastAPI + admin routes
│   ├── ui/             # Interfaz Streamlit (app.py + chat_app.py + admin_dashboard.py)
│   ├── analytics/      # Sistema de tracking y métricas
│   ├── memory/         # Gestión de memoria conversacional
│   ├── predictive/     # Motor predictivo y recomendaciones
│   ├── admin/          # Gestión de documentos y feedback
│   └── evaluation/     # Métricas y evaluación offline
├── reingest.py                 # Script de reingesta completa
├── reset_knowledge.py          # Script para limpiar vector store
├── run_analytics_dashboard.py  # Script para lanzar dashboard de analytics
├── run_admin_dashboard.py      # Script para lanzar panel de administración
├── test_api.py                 # Diagnóstico del sistema
├── REINGESTA.md                # Guía detallada de reingesta
├── ANALYTICS.md                # Documentación del sistema de métricas
├── MEMORIA_CONVERSACIONAL.md   # Documentación de memoria conversacional
├── SISTEMA_PREDICTIVO.md       # Documentación del motor predictivo
├── ADMIN.md                    # Documentación del sistema de administración
└── MANUAL_USO_RAPIDO.md        # 📖 Manual rápido para usuarios y administradores
```

---

## 🚀 Instalación y Configuración

### 1️⃣ Prerrequisitos

**Software:**
- Python 3.10 o superior
- Git
- **Ollama instalado** (para el modelo LLM local)
  - Descarga desde: https://ollama.com
  - Compatible con Windows, macOS y Linux
  - Instala y asegúrate de que esté corriendo
- Conexión a internet (solo para la instalación inicial y descarga de modelos)

**Hardware recomendado:**
- **Mínimo:** 8GB RAM, CPU moderna (puede funcionar solo con CPU)
- **Recomendado:** 16GB+ RAM, GPU con 6GB+ VRAM (NVIDIA/AMD/Apple Silicon)
- **Óptimo:** 32GB RAM, GPU con 8GB+ VRAM

**Nota sobre modelos:**
- `llama3.1:8b-instruct-q4_K_M` (recomendado): ~5GB de RAM/VRAM
- `llama3.2:3b` (alternativa ligera): ~2GB de RAM/VRAM
- Sin GPU: El modelo funcionará en CPU, será más lento pero funcional

### 2️⃣ Clonar el repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd org-assistant
```

### 3️⃣ Crear entorno virtual

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 4️⃣ Instalar dependencias

```bash
pip install -e .
```

Para desarrollo (incluye pytest, ruff):
```bash
pip install -e ".[dev]"
```

### 5️⃣ Configurar variables de entorno

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

**⚠️ IMPORTANTE:** Antes de continuar, asegúrate de tener Ollama corriendo y descarga el modelo:

```bash
# Verifica que Ollama esté instalado
ollama --version

# Descarga el modelo recomendado (Llama 3.1 8B cuantizado)
ollama pull llama3.1:8b-instruct-q4_K_M

# Verifica que el modelo esté disponible
ollama list
```

El archivo `.env` ya tiene la configuración correcta por defecto:
- `OLLAMA_BASE_URL=http://localhost:11434` (puerto por defecto de Ollama)
- `OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M` (modelo recomendado)

### 6️⃣ Agregar documentos

Coloca tus documentos organizacionales en `data/raw/`:

```bash
data/raw/
├── politicas/
│   └── trabajo_remoto.pdf
├── procedimientos/
│   └── reembolsos.md
└── ejemplo_documento.txt  # ← Ya incluido como ejemplo
```

**Formatos soportados:** `.txt`, `.md`, `.pdf`, `.docx`, `.csv`, `.json`

> 💡 **Tip:** Organiza los documentos en subcarpetas por proceso/departamento para facilitar filtros de búsqueda.

### 7️⃣ Ejecutar ingesta inicial

```bash
python reingest.py
```

Este script:
- Procesa todos los documentos de `data/raw/`
- Extrae keywords con TF-IDF
- Genera embeddings
- Construye el vector store

⏱️ **Tiempo estimado:** 2-5 minutos (depende de cantidad de documentos)

### 8️⃣ Verificar instalación

```bash
python test_api.py
```

Si todos los tests pasan ✅, estás listo para usar el sistema.

### 9️⃣ Verificar que hay documentos en el vector store

```bash
python check_docs.py
```

Este script muestra cuántos documentos hay en tu base de conocimientos. Si sale 0, ejecuta `python reingest.py`.

---

## 🔒 Confirmación de Modelo Local (100% Privado)

Tu asistente funciona **completamente en local** sin enviar datos a internet:

### ✅ Cómo verificarlo:

**1. Revisa la configuración actual:**
```bash
python -c "from config.settings import get_settings; s = get_settings(); print(f'Modelo: {s.ollama_model}'); print(f'URL: {s.ollama_base_url}')"
```

Deberías ver:
```
Modelo: llama3.1:8b-instruct-q4_K_M
URL: http://localhost:11434
```

**2. Monitorea el uso de recursos:**
- Abre el monitor de sistema de tu SO (Administrador de Tareas en Windows, Activity Monitor en Mac, htop en Linux)
- Observa el uso de CPU/GPU mientras haces una consulta
- Verás un pico de uso porque el modelo se ejecuta localmente en tu máquina

**3. Prueba sin internet:**
- Desconecta tu WiFi
- Haz una consulta
- Funcionará perfectamente porque todo es local

**Garantías de privacidad:**
- ✅ Ningún dato sale de tu máquina
- ✅ No hay API keys de servicios externos
- ✅ Puedes apagar Ollama cuando no lo uses
- ✅ El modelo se ejecuta 100% en tu hardware local (CPU/GPU)

---

## 🎯 Uso del Sistema

> 📖 **¿Primera vez usando el sistema?** Lee el [**MANUAL DE USO RÁPIDO**](MANUAL_USO_RAPIDO.md) - Guía paso a paso para usuarios y administradores.

### Iniciar los servicios

**Terminal 1 - Servidor API:**
```bash
uvicorn src.service.app:app --reload
```

**Terminal 2 - Interfaz Streamlit (Básica):**
```bash
streamlit run src/ui/app.py
```

**O Terminal 2 - Interfaz de Chat (Con memoria conversacional):**
```bash
python run_chat.py
```

**Terminal 3 (Opcional) - Dashboard de Analytics:**
```bash
python run_analytics_dashboard.py
```

**Terminal 4 (Opcional) - Panel de Administración:**
```bash
python run_admin_dashboard.py
```

### Acceder a la interfaz

Abre tu navegador en:
- **UI Básica:** http://localhost:8501
- **Chat con Memoria:** http://localhost:8503
- **Analytics Dashboard:** http://localhost:8502
- **Admin Dashboard:** http://localhost:8504
- **API Docs:** http://localhost:8000/docs
- **API Analytics:** http://localhost:8000/analytics?days=7
- **API Predictivo:** http://localhost:8000/predictive/insights?days=7
- **API Recomendaciones:** http://localhost:8000/predictive/recommendations?question=vacaciones
- **API Alertas:** http://localhost:8000/predictive/alerts
- **API Admin Docs:** http://localhost:8000/admin/documents
- **Health Check:** http://localhost:8000/health

### Hacer preguntas

Desde la interfaz Streamlit:
1. Escribe tu pregunta (ej: "¿Cuál es el proceso para solicitar vacaciones?")
2. (Opcional) Agrega filtros por proceso o responsable
3. Haz clic en "Consultar"
4. Revisa la respuesta y las referencias a documentos
5. Proporciona feedback (útil/no útil) para mejorar el sistema

### Usar el Chat con Memoria Conversacional

La nueva interfaz de chat (http://localhost:8503) permite:
- **Conversaciones naturales:** El asistente recuerda el contexto
- **Preguntas de seguimiento:** "¿Y si...?", "Dame más detalles sobre eso"
- **Historial persistente:** Mantiene la conversación activa durante 24 horas
- **Referencias inline:** Ve las fuentes sin salir del chat
- **Limpiar chat:** Reinicia la conversación cuando quieras

Ejemplo de conversación:
```
Usuario: ¿Cuál es el proceso de solicitud de vacaciones?
Asistente: [Responde con el proceso completo]

Usuario: ¿Y si necesito más de 15 días?
Asistente: [Responde considerando el contexto anterior]

Usuario: ¿Quién debe aprobar la solicitud?
Asistente: [Responde con información específica del proceso]
```

### Monitorear métricas de uso

Desde el Dashboard de Analytics (http://localhost:8502):
- **KPIs principales:** Consultas totales, satisfacción, cobertura, tiempo de respuesta
- **Volumen:** Tendencia de consultas por día
- **Satisfacción:** Tendencia y gauge de satisfacción del usuario
- **Top consultas:** Preguntas más frecuentes
- **Top temas:** Procesos más consultados
- **Cobertura:** Distribución de consultas exitosas vs fallidas
- **Impacto organizacional:** Tiempo ahorrado, eficiencia del sistema
- **Recomendaciones:** Sugerencias automáticas de mejora

### Gestionar Ollama (liberar recursos cuando no lo uses)

Ollama consume recursos solo durante las consultas. Para liberar completamente la memoria:

**Windows:**
```bash
# Cerrar desde el Administrador de Tareas o:
taskkill /IM ollama.exe /F

# Para reiniciar: busca "Ollama" en el menú inicio
```

**macOS:**
```bash
# Detener:
brew services stop ollama

# Iniciar:
brew services start ollama
```

**Linux:**
```bash
# Detener:
sudo systemctl stop ollama

# Iniciar:
sudo systemctl start ollama
```

---

## ⚙️ Panel de Administración

### Gestión de Documentos sin Código

El sistema incluye un **Panel de Administración** completo para gestionar documentos sin necesidad de conocimientos técnicos:

**Acceso:**
```bash
python run_admin_dashboard.py
# Abre en: http://localhost:8504
```

**Funcionalidades:**

1. **📁 Gestión de Documentos:**
   - Subir documentos (.txt, .md, .pdf, .docx, .doc)
   - Listar todos los documentos indexados
   - Eliminar documentos obsoletos
   - Ver estadísticas del sistema
   - Re-ingesta automática tras cambios

2. **💬 Gestión de Feedback:**
   - Revisar feedback negativo
   - Categorizar problemas (info faltante, respuesta incorrecta, poco clara)
   - Marcar como accionado con notas
   - Ver top temas con problemas

3. **📊 Estadísticas:**
   - Tasa de satisfacción del usuario
   - Total de feedback positivo/negativo
   - Feedback pendiente de revisión
   - Distribución por categoría

**Ventajas del Panel de Admin:**
- ✅ Sin necesidad de editar código o reiniciar servidor
- ✅ Cambios reflejados inmediatamente
- ✅ Detección automática de duplicados
- ✅ Loop de mejora continua con feedback
- ✅ Interface intuitiva para usuarios no técnicos

📖 **Documentación completa:** Ver [ADMIN.md](ADMIN.md)

**⚠️ Nota sobre documentos existentes:**
Si tienes documentos en `data/raw/` que fueron agregados **antes** de usar el panel de admin, necesitas registrarlos:
```bash
python register_existing_docs.py
```
Esto solo es necesario una vez. Los documentos subidos mediante el panel se registran automáticamente.

---

## 🔄 Actualizar Documentos (Método Manual)

### Reingesta completa (desde cero)

**Nota:** Este método es para usuarios técnicos. **Se recomienda usar el Panel de Administración** (ver sección anterior).

```bash
# 1. Resetear base de conocimientos
python reset_knowledge.py

# 2. Actualizar/agregar documentos en data/raw/

# 3. Reingestar todo
python reingest.py

# 4. Reiniciar servidor FastAPI (Ctrl+C y volver a ejecutar)
```

📖 **Más detalles:** Ver [REINGESTA.md](REINGESTA.md)

---

## 🐛 Solución de Problemas

### Error: "No se puede conectar con Ollama"

**Solución:** Asegúrate de que Ollama esté corriendo y el modelo esté descargado.

```bash
# Verificar que Ollama esté corriendo
ollama list

# Si no está instalado, descarga desde: https://ollama.com

# Descargar el modelo si no está disponible
ollama pull llama3.1:8b-instruct-q4_K_M
```

### Error: "El vector store no se ha inicializado"

**Solución:** Ejecuta la ingesta:

```bash
python reingest.py
```

### Error: "Internal Server Error" en Streamlit

**Solución:** Revisa los logs del servidor FastAPI. Causas comunes:
- El vector store no existe → Ejecuta `python reingest.py`
- Ollama no está corriendo → Verifica con `ollama list`
- El modelo no está descargado → Ejecuta `ollama pull llama3.1:8b-instruct-q4_K_M`
- Falta alguna dependencia → Ejecuta `pip install -e .`

### Los documentos no se reflejan en las respuestas

**Solución:** Debes reingestar Y reiniciar el servidor:

```bash
python reingest.py
# Luego Ctrl+C en el servidor y volver a ejecutar:
uvicorn src.service.app:app --reload
```

### Diagnóstico completo del sistema

```bash
python test_api.py
```

Este script verifica:
- ✅ Configuración cargada correctamente
- ✅ Vector store funcional
- ✅ Conexión con Ollama (modelo local)
- ✅ Pipeline completo end-to-end

---

## 📚 Scripts Útiles

| Script | Descripción |
|--------|-------------|
| `python reingest.py` | Reingesta completa de documentos |
| `python reset_knowledge.py` | Limpia vector store y procesados |
| `python test_api.py` | Diagnóstico completo del sistema |
| `python run_chat.py` | Lanzar chat con memoria conversacional |
| `python run_analytics_dashboard.py` | Lanzar dashboard de analytics |
| `uvicorn src.service.app:app --reload` | Iniciar servidor API |
| `streamlit run src/ui/app.py` | Iniciar interfaz web básica |

---

## 🤝 Contribución al Proyecto

### Para el equipo de desarrollo

1. **Crea una rama para tu feature:**
   ```bash
   git checkout -b feature/nombre-descriptivo
   ```

2. **Instala dependencias de desarrollo:**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Ejecuta los tests antes de hacer commit:**
   ```bash
   pytest
   ruff check .
   ```

4. **Haz commit y push:**
   ```bash
   git add .
   git commit -m "Descripción clara del cambio"
   git push origin feature/nombre-descriptivo
   ```

---

## ⚙️ Configuración Avanzada

### Cambiar el tamaño de chunks

Edita `src/knowledge_base/ingest.py`:

```python
DEFAULT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # Caracteres por chunk
    chunk_overlap=150,    # Solapamiento entre chunks
)
```

### Cambiar el modelo de embeddings

Edita `.env`:

```bash
# Para mejor soporte multilingüe/español:
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

**⚠️ Importante:** Si cambias el modelo de embeddings, debes hacer una reingesta completa.

### Cambiar el modelo LLM

Primero descarga el modelo con Ollama:

```bash
# Modelo más pequeño y rápido (3B):
ollama pull llama3.2:3b

# Modelo equilibrado (recomendado, 8B):
ollama pull llama3.1:8b-instruct-q4_K_M

# Modelo más grande y preciso (7B):
ollama pull mistral:7b
```

Luego edita `.env`:

```bash
# Ejemplo para cambiar al modelo más pequeño:
OLLAMA_MODEL=llama3.2:3b

# O al modelo Mistral:
OLLAMA_MODEL=mistral:7b
```

---

## 📝 Notas Importantes

- **Seguridad:** Nunca subas el archivo `.env` al repositorio (está en `.gitignore`)
- **Datos:** Los documentos en `data/raw/` NO se suben al repo por defecto (solo ejemplos)
- **Modelo Local:** El modelo LLM se ejecuta localmente en tu máquina. Asegúrate de tener Ollama corriendo
- **Recursos:** El modelo 8B cuantizado usa ~5GB de VRAM/RAM. Puedes usar modelos más pequeños (3B) si tienes recursos limitados
- **Performance:** El primer arranque descarga modelos (~90MB embeddings + ~5GB LLM), es normal que tome tiempo
- **Feedback:** El sistema guarda feedback en `data/feedback/feedback.jsonl` para análisis

---

## 🔗 Enlaces Útiles

- [Descargar Ollama](https://ollama.com)
- [Modelos disponibles en Ollama](https://ollama.com/library)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)

---

## 👥 Equipo

**UDLA Prototype Team**

Para preguntas o soporte, contacta al equipo de desarrollo.

---

## 📄 Licencia

MIT License - Ver archivo LICENSE para más detalles.

---

¿Preguntas? Revisa [REINGESTA.md](REINGESTA.md) para más detalles sobre el manejo de documentos.
