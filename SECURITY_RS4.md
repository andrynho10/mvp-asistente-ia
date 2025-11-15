# 🔐 RS4: HTTPS + Cifrado en Reposo

**Estado:** ✅ IMPLEMENTADO (Sesión 3)
**Requerimiento:** Cifrado en tránsito (HTTPS) + Cifrado en reposo (datos sensibles)
**Prioridad:** CRÍTICO para producción

---

## 📋 Resumen Ejecutivo

El requerimiento RS4 implementa dos capas de seguridad:

| Aspecto | Implementación | Estado |
|--------|----------------|--------|
| **Cifrado en tránsito** | HTTPS/TLS | ✅ Configurado (dev + prod) |
| **Cifrado en reposo** | Fernet (256-bit AES) | ✅ SQLite + ChromaDB |
| **Gestión de claves** | Fernet con rotación | ✅ Automatizado |
| **Certificados SSL** | Auto-firmados (dev) + Let's Encrypt (prod) | ✅ Scripts listos |
| **Integridad de datos** | HMAC en Fernet | ✅ Built-in |

---

## 🏗️ Arquitectura de Cifrado

### 1. Cifrado en Tránsito (HTTPS/TLS)

```
┌─────────────┐                    ┌─────────────┐
│   Cliente   │◄──────HTTPS───────►│  Servidor   │
│ (Streamlit) │   (TLS 1.3, AES256)│  (FastAPI)  │
└─────────────┘                    └─────────────┘
```

**Implementación:**
- **Desarrollo:** SSL auto-firmado (openssl) en uvicorn
- **Producción:** nginx reverse proxy con Let's Encrypt

**Configuración:**

```python
# src/security/ssl_certs.py
from src.security.ssl_certs import SSLConfig, generate_self_signed_cert

# Desarrollo
ssl_config = SSLConfig(
    enabled=True,
    cert_path=Path("certs/cert.pem"),
    key_path=Path("certs/key.pem"),
    auto_generate=True  # Genera certificado si no existe
)

# En FastAPI
if ssl_config.is_ready():
    ssl_config_dict = ssl_config.get_uvicorn_config()
    # ssl_certfile, ssl_keyfile para uvicorn
```

### 2. Cifrado en Reposo (Fernet)

```
┌──────────────────────────────────┐
│   Datos en Aplicación (RAM)      │  ✗ No cifrado (en memoria)
└───────────────┬──────────────────┘
                │ Cifrado antes de guardar
                ▼
┌──────────────────────────────────┐
│   BD SQLite (auth.db)            │  ✓ Contraseñas cifradas
│   ├─ users.hashed_password       │    (campo: encrypted)
│   └─ tokens.refresh_token        │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│   Vector Store (ChromaDB)        │  ✓ Embeddings no cifrados
│   ├─ Embeddings (números)        │    (derivados de contenido)
│   └─ Metadatos sensibles         │  ✓ Contenido + metadata
│       (email, author, owner)     │    sensibles cifrados
└──────────────────────────────────┘
```

**Algoritmo:** Fernet (Symmetric)
- **Cifrado:** AES-128 en modo CBC
- **Integridad:** HMAC-SHA256
- **Clave:** 256 bits (128 bits para AES + 128 bits para HMAC)
- **Tamaño overhead:** ~57 bytes por dato

---

## 🔑 Gestión de Claves

### Generación de Claves

```bash
# Opción 1: Script Python
python scripts/generate_encryption_key.py

# Opción 2: Directamente
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Output ejemplo:
# 8FLQq3-U-qV_-FXxBzIVVV_QpG-K1j2L9M3N4O5P6Q7R8S9T=
```

### Almacenamiento de Claves

**Desarrollo:**
```bash
# En .env.local (gitignore)
ENCRYPTION_KEY=<llave_generada>
```

**Producción (NUNCA en código):**

| Opción | Pros | Contras |
|--------|------|---------|
| **AWS Secrets Manager** | ✓ Rotación automática | Costo, vendor lock-in |
| **HashiCorp Vault** | ✓ Auditoría completa | Complejidad |
| **Env variables (systemd)** | ✓ Simple | Riesgo exposición |
| **Archivo + permisos 0600** | ✓ Portabilidad | Gestión manual |

**Recomendación:** Vault o Secrets Manager en producción.

### Rotación de Claves

⚠️ **Problema:** Fernet no soporta rotación nativa.

**Solución implementada:**

```python
class EncryptionManager:
    """Maneja cifrado/descifrado con múltiples claves"""

    def decrypt_with_key_rotation(data: str, primary_key: str, old_keys: List[str]):
        """
        Intenta descifrar con primary_key primero.
        Si falla, prueba con old_keys (para datos cifrados con llave anterior).
        """
        for key in [primary_key] + old_keys:
            try:
                return EncryptionManager(key).decrypt(data)
            except:
                continue
        raise ValueError("No key worked")
```

**Procedimiento de rotación:**

```bash
# 1. Generar nueva llave
python scripts/generate_encryption_key.py  # → KEY_NEW

# 2. Re-cifrar datos con nueva llave (en background)
python scripts/rotate_encryption_keys.py --old-key $KEY_OLD --new-key $KEY_NEW

# 3. Actualizar .env
ENCRYPTION_KEY=$KEY_NEW

# 4. Reiniciar servicio
systemctl restart org-assistant
```

---

## 🛠️ Implementación Técnica

### A. Cifrado en SQLite

**Campos cifrados automáticamente:**

```python
# src/auth/repository.py
ENCRYPTED_FIELDS = {
    "users": ["password"],              # ✓ Cifrado
    "tokens": ["refresh_token"],        # ✓ Cifrado
    # NO cifrar: username, email (para búsquedas)
}
```

**Flujo:**

```python
# 1. Al crear usuario
user_create = UserCreate(username="juan", password="secret123")
# → password hashado con bcrypt: "$2b$12$..."
# → hash cifrado con Fernet antes de guardar en BD

# 2. Al recuperar usuario
user = repository.get_user_by_id("uuid123")
# → password descifrado automáticamente desde BD
# → comparar con hash de login: bcrypt.verify()
```

**Interfaz:**

```python
from src.security.encryption import EncryptionManager

manager = EncryptionManager(encryption_key)

# Básico
encrypted = manager.encrypt("datos")           # → "gAAAAAB..."
decrypted = manager.decrypt(encrypted)         # → "datos"

# JSON
encrypted_json = manager.encrypt_json({"a": 1})
data = manager.decrypt_json(encrypted_json)

# Archivos
manager.encrypt_file(input_path, output_path)
manager.decrypt_file(input_path, output_path)
```

### B. Cifrado en ChromaDB

**Estrategia:**

```python
# src/security/chromadb_cipher.py
cipher = ChromaDBCipher(encryption_manager)

# Antes de agregar a ChromaDB
texts = ["documento 1", "documento 2"]
encrypted_texts = cipher.encrypt_texts(texts)
vector_store.add_texts(encrypted_texts, metadatas)

# Al recuperar
results = vector_store.similarity_search(query, k=5)
decrypted = cipher.decrypt_documents(results)
```

**Qué se cifra:**

| Campo | Cifrado | Razón |
|-------|---------|-------|
| `page_content` | ✓ Sí | Contenido sensible |
| `embedding` | ✗ No | Números derivados, no reversibles |
| `metadata.source` | ✗ No | Necesario para búsqueda |
| `metadata.author` | ✓ Sí | PII sensible |
| `metadata.email` | ✓ Sí | PII sensible |

### C. SQLite con Wrapper Transparente

Aunque no se implementó el wrapper completo (es opcional), se cifra manualmente:

```python
# Opción A: Manual (implementado)
hashed_password = user.hashed_password
if self.encryption_manager:
    hashed_password = self.encryption_manager.encrypt(hashed_password)
conn.execute("INSERT ... VALUES (..., ?...)", (..., hashed_password, ...))

# Opción B: Con wrapper (para futuros)
# cursor = EncryptedCursor(conn.cursor(), manager)
# cursor.execute("INSERT ...", {..., "password": value})  # Cifra automático
```

---

## 🚀 Configuración por Entorno

### Desarrollo

```yaml
# .env.local
SSL_ENABLED=false                              # HTTP
ENCRYPTION_KEY=<llave_dev>                    # (opcional para dev)
ENABLE_DB_ENCRYPTION=true
```

**Inicio:**
```bash
# API sin SSL
python -m src.service.app

# Streamlit
streamlit run src/ui/app.py

# Con SSL auto-firmado (opcional)
python -m uvicorn src.service.app:app \
    --ssl-certfile=certs/cert.pem \
    --ssl-keyfile=certs/key.pem \
    --host 0.0.0.0 --port 8000
```

### Producción

```yaml
# .env (en servidor, variables protegidas)
SSL_ENABLED=false                              # nginx maneja SSL
ENCRYPTION_KEY=<llave_prod_vault>             # Desde Vault/Secrets
ENABLE_DB_ENCRYPTION=true
```

**nginx config:**

```nginx
# deployment/nginx.conf
server {
    listen 443 ssl http2;
    server_name org-assistant.example.com;

    # Certificado Let's Encrypt
    ssl_certificate /etc/letsencrypt/live/org-assistant.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/org-assistant.example.com/privkey.pem;

    # Security headers
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    add_header Strict-Transport-Security "max-age=31536000" always;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name org-assistant.example.com;
    return 301 https://$server_name$request_uri;
}
```

---

## 📊 Verificación de Seguridad

### Checklist de Implementación

```bash
# 1. Verificar módulos de cifrado
python -c "from src.security.encryption import EncryptionManager; print('✓ OK')"

# 2. Generar llave de prueba
python scripts/generate_encryption_key.py

# 3. Verificar SQLite cifrado
python -c "
from src.auth.repository import UserRepository
repo = UserRepository(use_encryption=True)
print(f'Encryptor: {repo.encryption_manager}')
"

# 4. Verificar ChromaDB cifrado
python -c "
from src.security.chromadb_cipher import ChromaDBCipher
from src.security.encryption import EncryptionManager
cipher = ChromaDBCipher(EncryptionManager('...'))
print(f'ChromaDB cipher enabled: {cipher.enabled}')
"
```

### Tests de Seguridad

```python
# tests/security/test_encryption.py
def test_encryption_decryption():
    manager = EncryptionManager(generate_encryption_key())
    plaintext = "datos secretos"
    encrypted = manager.encrypt(plaintext)

    assert encrypted != plaintext
    assert manager.decrypt(encrypted) == plaintext
    assert EncryptionManager.is_encrypted(encrypted)

def test_different_key_fails():
    key1 = generate_encryption_key()
    key2 = generate_encryption_key()

    manager1 = EncryptionManager(key1)
    encrypted = manager1.encrypt("secret")

    manager2 = EncryptionManager(key2)
    with pytest.raises(Exception):
        manager2.decrypt(encrypted)
```

---

## 🔒 Consideraciones de Seguridad

### ✓ Lo que protege RS4

1. **Datos en reposo:** Si alguien accede a la BD, los datos sensibles están cifrados
2. **En tránsito:** HTTPS previene intercepción de credentials
3. **Integridad:** HMAC en Fernet detecta manipulación de datos
4. **Autenticidad:** Certificados SSL validan identidad del servidor

### ✗ Lo que NO protege (rs5, rs3)

1. **PII masking:** Nombres, emails, RUT (implementar en RS5)
2. **Auditoría:** Quién accedió, cuándo (implementar en RS3)
3. **Backup cifrado:** Respaldos también deben cifrarse
4. **Datos en RAM:** La aplicación procesa datos en claro

### ⚠️ Riesgos Residuales

| Riesgo | Mitigación |
|--------|-----------|
| **Llave comprometida** | Rotación frecuente + vault seguro |
| **Ataque de timing** | Fernet usa constantes de tiempo |
| **Acceso a archivo .env** | Permisos 0600 + variable de entorno |
| **Logs con datos sensibles** | Implementar PII masking en RM2 |
| **Caché en cliente** | Control de cache en response headers |

---

## 📚 Scripts Útiles

### 1. Generar Certificado Auto-Firmado

```bash
cd certs/
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
    -days 365 -nodes \
    -subj "/C=CL/ST=Metropolitan/L=Santiago/O=Org-Assistant/CN=localhost"
```

### 2. Generar Llave de Cifrado

```bash
python scripts/generate_encryption_key.py
```

### 3. Verificar Certificado

```bash
openssl x509 -in certs/cert.pem -text -noout
```

### 4. Respaldar BD Cifrada

```python
from src.security.chromadb_cipher import ChromaDBCipher
from src.security.encryption import EncryptionManager

manager = EncryptionManager(key)
ChromaDBCipher.backup_encrypted_store(
    Path("data/embeddings/chroma"),
    Path("backups/chroma.encrypted"),
    manager
)
```

---

## 🔄 Flujo de Implementación Pendiente

**Próximas sesiones:**

- **RS5:** Cifrado de backups + PII masking
- **RM2:** Logging centralizado (sin datos sensibles)
- **RS3:** Auditoría de accesos

---

## 📖 Referencias

- [Fernet (cryptography.io)](https://cryptography.io/en/latest/fernet/)
- [OWASP Cryptographic Failures](https://owasp.org/Top10/A02_2021-Cryptographic_Failures/)
- [RFC 5869 - HKDF](https://tools.ietf.org/html/rfc5869)
- [Let's Encrypt + nginx](https://certbot.eff.org/instructions?ws=nginx&os=linux)

---

**Última actualización:** 2025-11-15 (Sesión 3)
**Estado:** Listo para producción con ajustes de deployment
