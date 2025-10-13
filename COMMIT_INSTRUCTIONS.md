# 📝 Instrucciones para Subir al Repositorio

## ✅ Archivos listos para commit

Los siguientes archivos han sido actualizados/creados y están listos para subir:

### Archivos corregidos (bugs fixed):
- `src/service/app.py` - Corregida importación de Chroma + deserialización de keywords
- `src/rag_engine/vector_store.py` - Eliminado método deprecated `persist()`
- `pyproject.toml` - Agregadas dependencias faltantes

### Nuevos archivos de utilidad:
- `reingest.py` - Script completo de reingesta
- `reset_knowledge.py` - Script para limpiar base de conocimientos
- `test_api.py` - Diagnóstico del sistema
- `REINGESTA.md` - Documentación detallada del proceso de ingesta

### Configuración para el equipo:
- `.env.example` - Plantilla de configuración (NUEVO)
- `.gitignore` - Actualizado para proteger datos sensibles
- `data/raw/.gitkeep` - Mantiene estructura de directorios
- `data/raw/ejemplo_documento.txt` - Documento de ejemplo

### Documentación:
- `README_NUEVO.md` - README actualizado con instrucciones completas

---

## 🚀 Pasos para hacer el commit y push

### 1. Reemplazar README

**IMPORTANTE:** Antes de hacer commit, reemplaza el README antiguo con el nuevo:

```bash
# Windows (PowerShell o CMD)
del README.md
ren README_NUEVO.md README.md

# Linux/Mac
rm README.md
mv README_NUEVO.md README.md
```

### 2. Verificar estado de Git

```bash
git status
```

Deberías ver estos archivos modificados/nuevos:
- Modified: `src/service/app.py`
- Modified: `src/rag_engine/vector_store.py`
- Modified: `pyproject.toml`
- Modified: `.gitignore`
- Modified: `README.md`
- New: `.env.example`
- New: `reingest.py`
- New: `reset_knowledge.py`
- New: `test_api.py`
- New: `REINGESTA.md`
- New: `data/raw/.gitkeep`
- New: `data/raw/ejemplo_documento.txt`

### 3. Revisar que NO se suban archivos sensibles

Verifica que estos archivos/carpetas NO aparezcan en git status:
- ❌ `.env` (contiene tu API key)
- ❌ `data/embeddings/` (vector store, muy pesado)
- ❌ `data/processed/` (archivos generados)
- ❌ `data/feedback/` (datos de usuario)
- ❌ `.venv/` (entorno virtual)

Si aparecen, es que el `.gitignore` no se aplicó correctamente.

### 4. Agregar archivos al staging

```bash
# Agregar todos los cambios
git add .

# O agregar selectivamente:
git add src/service/app.py
git add src/rag_engine/vector_store.py
git add pyproject.toml
git add .gitignore
git add README.md
git add .env.example
git add reingest.py reset_knowledge.py test_api.py
git add REINGESTA.md
git add data/raw/.gitkeep
git add data/raw/ejemplo_documento.txt
```

### 5. Crear commit

```bash
git commit -m "Fix: Corregir errores de compatibilidad y agregar herramientas de reingesta

- Fix: Actualizar importación de Chroma a langchain_chroma
- Fix: Eliminar método deprecated persist() en vector_store
- Fix: Deserializar keywords JSON en render_references
- Add: Agregar dependencias faltantes (langchain-chroma, langchain-huggingface)
- Add: Scripts de utilidad (reingest.py, reset_knowledge.py, test_api.py)
- Add: Documentación completa en README.md y REINGESTA.md
- Add: Plantilla .env.example para configuración
- Update: Mejorar .gitignore para proteger datos sensibles
- Add: Documento de ejemplo para nuevos usuarios"
```

### 6. Push al repositorio

```bash
# Si es tu primera vez con esta rama
git push -u origin main

# O simplemente
git push
```

---

## 📋 Checklist para tus compañeros

Una vez que hagas el push, tus compañeros deberán:

1. ✅ Clonar/actualizar el repositorio
   ```bash
   git clone <URL> o git pull
   ```

2. ✅ Crear entorno virtual
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. ✅ Instalar dependencias
   ```bash
   pip install -e .
   ```

4. ✅ Copiar .env.example a .env
   ```bash
   copy .env.example .env  # Windows
   ```

5. ✅ Obtener API key de Groq
   - Ir a: https://console.groq.com/keys
   - Crear cuenta gratis
   - Copiar API key al archivo .env

6. ✅ Agregar documentos en data/raw/

7. ✅ Ejecutar ingesta
   ```bash
   python reingest.py
   ```

8. ✅ Probar el sistema
   ```bash
   python test_api.py
   ```

9. ✅ Iniciar servicios
   ```bash
   # Terminal 1
   uvicorn src.service.app:app --reload

   # Terminal 2
   streamlit run src/ui/app.py
   ```

---

## ⚠️ Recordatorios importantes

### Para ti (antes del push):
- [ ] Reemplazar README.md con README_NUEVO.md
- [ ] Verificar que .env NO está en el commit
- [ ] Verificar que data/embeddings/ NO está en el commit
- [ ] Eliminar COMMIT_INSTRUCTIONS.md (este archivo) antes del commit

### Para el equipo (después del pull):
- [ ] Cada uno debe obtener su propia API key de Groq
- [ ] Nunca subir el archivo .env al repo
- [ ] Nunca subir documentos reales de la organización a data/raw/

---

## 🎉 Listo!

Una vez completados estos pasos, el proyecto estará disponible para todo el equipo.

Si hay problemas, el archivo test_api.py ayudará a diagnosticar rápidamente.
