# 🔄 Guía de Reingesta de Documentos

Esta guía explica cómo reiniciar el sistema y hacer una reingesta completa de documentos.

---

## 📋 Escenarios de uso

### Opción 1: Reingesta completa (resetear todo y volver a empezar)

Usa esto cuando:
- Quieres que el sistema "olvide" todo lo aprendido
- Has actualizado/modificado los documentos RAW
- Quieres cambiar la configuración de chunking o embeddings

**Pasos:**

```bash
# 1. Resetear la base de conocimientos
python reset_knowledge.py

# 2. (Opcional) Actualizar documentos en data/raw/

# 3. Ejecutar reingesta completa
python reingest.py

# 4. Reiniciar el servidor FastAPI
# Ctrl+C en la terminal del servidor y volver a ejecutar:
uvicorn src.service.app:app --reload
```

---

### Opción 2: Solo actualizar documentos (mantener vector store existente)

Usa esto cuando:
- Solo quieres agregar nuevos documentos sin borrar los existentes
- Los documentos existentes no han cambiado

**Pasos:**

```bash
# 1. Agregar nuevos documentos a data/raw/

# 2. Procesar documentos
python -m src.knowledge_base.ingest

# 3. Actualizar vector store (agregará los nuevos chunks)
python reingest.py

# 4. Reiniciar el servidor FastAPI
```

---

## 📁 Estructura de directorios

```
org-assistant/
├── data/
│   ├── raw/                      # 📂 Coloca tus documentos aquí
│   │   ├── politicas/
│   │   │   └── politica_datos.txt
│   │   ├── procedimientos/
│   │   │   └── reembolsos.md
│   │   └── incidentes/
│   │       └── casos_historicos.csv
│   │
│   ├── processed/                # 📝 Documentos procesados (chunks)
│   │   └── knowledge_chunks.jsonl
│   │
│   └── embeddings/               # 🗄️ Vector store (embeddings)
│       └── chroma/
│           └── chroma.sqlite3
```

---

## 🛠️ Formatos de documentos soportados

- `.txt` - Archivos de texto plano
- `.md` - Markdown
- `.pdf` - PDFs (requiere `pypdf`)
- `.docx` - Word (requiere `docx2txt`)
- `.csv` - CSV (se convierte a tabla de texto)
- `.json` - JSON (se formatea con indentación)

---

## ⚙️ Personalizar la ingesta

### Cambiar el tamaño de los chunks

Edita [src/knowledge_base/ingest.py:36-40](src/knowledge_base/ingest.py#L36-L40):

```python
DEFAULT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # ← Cambiar aquí (caracteres por chunk)
    chunk_overlap=150,    # ← Solapamiento entre chunks
    separators=["\n\n", "\n", " ", ""],
)
```

### Cambiar el modelo de embeddings

Edita [.env](.env):

```bash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2  # Modelo actual (rápido, inglés)
# Alternativas:
# EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2  # Multilingüe
# EMBEDDING_MODEL=BAAI/bge-base-en-v1.5  # Mejor calidad, más lento
```

**Nota:** Si cambias el modelo de embeddings, DEBES hacer una reingesta completa (Opción 1).

---

## 🔍 Verificar el estado del sistema

```bash
# Ver qué documentos están en RAW
ls data/raw/

# Ver cuántos chunks se procesaron
python -c "import json; chunks = open('data/processed/knowledge_chunks.jsonl').readlines(); print(f'{len(chunks)} chunks procesados')"

# Verificar que el vector store existe
ls data/embeddings/chroma/

# Probar el sistema end-to-end
python test_api.py
```

---

## ⚠️ Solución de problemas

### Error: "No se encontraron documentos en la carpeta raw/"

**Solución:** Coloca al menos un documento soportado en `data/raw/`

### Error: "El vector store no se ha inicializado"

**Solución:** Ejecuta `python reingest.py` para construir el vector store

### Error al cargar PDFs o DOCX

**Solución:** Instala las dependencias faltantes:

```bash
pip install pypdf docx2txt
```

### El sistema no refleja los cambios en los documentos

**Solución:** Ejecuta una reingesta completa (Opción 1) y reinicia el servidor

---

## 📊 Metadata de los documentos

Cada chunk incluye automáticamente:

- `source`: Ruta relativa del documento
- `document_id`: Nombre del archivo (sin extensión)
- `process`: Nombre de la carpeta padre (ej: "politicas", "procedimientos")
- `chunk_id`: ID único del chunk
- `keywords`: Palabras clave extraídas con TF-IDF

Puedes usar estos campos para filtrar búsquedas desde Streamlit.

---

## 🎯 Mejores prácticas

1. **Organiza tus documentos por proceso** en subcarpetas de `data/raw/` (ej: `politicas/`, `rrhh/`, `ti/`)
   - Esto permite filtrar por proceso en las búsquedas

2. **Usa nombres descriptivos** para los archivos
   - El nombre se usa como `document_id` en los metadatos

3. **Mantén los documentos actualizados** en `data/raw/`
   - Nunca modifiques `data/processed/` o `data/embeddings/` manualmente

4. **Haz backup de `data/raw/`** antes de cambios importantes
   - Es la única fuente de verdad del sistema

5. **Reinicia el servidor** después de cada reingesta
   - El servidor cachea el vector store en memoria

---

## 🚀 Flujo de trabajo recomendado

```bash
# 1. Desarrollo: Actualizar documentos
# Edita/agrega archivos en data/raw/

# 2. Hacer reingesta
python reingest.py

# 3. Probar el sistema
python test_api.py

# 4. Si los tests pasan, reiniciar servidor
# Ctrl+C en terminal del servidor
uvicorn src.service.app:app --reload

# 5. Probar desde Streamlit
streamlit run src/ui/app.py
```

---

## 📝 Scripts disponibles

| Script | Descripción |
|--------|-------------|
| `reset_knowledge.py` | Elimina vector store y procesados (mantiene RAW) |
| `reingest.py` | Procesa documentos y construye vector store |
| `test_api.py` | Diagnóstico completo del sistema |

---

¿Dudas? Revisa los logs del sistema o ejecuta `python test_api.py` para diagnóstico detallado.
