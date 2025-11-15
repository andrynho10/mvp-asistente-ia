# 🔐 Flujo de Autenticación - Asistente Organizacional

**Documento:** AUTH_FLOW.md
**Versión:** 1.0
**Fecha:** 2025-11-15
**Estado:** Implementado

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Arquitectura de Autenticación](#arquitectura-de-autenticación)
3. [Componentes Principales](#componentes-principales)
4. [Flujos de Usuario](#flujos-de-usuario)
5. [Gestión de Tokens](#gestión-de-tokens)
6. [Roles y Permisos](#roles-y-permisos)
7. [Configuración](#configuración)
8. [Guía de Uso](#guía-de-uso)
9. [Seguridad](#seguridad)

---

## Resumen Ejecutivo

La autenticación en el Asistente Organizacional utiliza **JWT (JSON Web Tokens)** con contraseñas hasheadas con **bcrypt**. El sistema implementa:

- ✅ **Autenticación:** JWT con HS256 (RS1)
- ✅ **Autorización:** RBAC basado en 4 roles (RS2)
- ✅ **Almacenamiento:** SQLite con usuarios y permisos
- ✅ **Sesiones:** Tokens con expiración configurable
- ⚠️ **Próximas:** Cifrado en tránsito (HTTPS) y en reposo (RS4, RS5)

---

## Arquitectura de Autenticación

### Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────────┐
│                    Cliente (Streamlit)                       │
│                                                               │
│  1. Login Form → POST /auth/login                           │
│  2. Token Response ← { access_token, user, expires_in }    │
│  3. Store Token en session_state                             │
│  4. Requests con Header: Authorization: Bearer <token>       │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI (Backend)                         │
│                                                               │
│  1. GET /auth/login → validate credentials                  │
│  2. Hash password con bcrypt                                 │
│  3. Create JWT token (HS256)                                 │
│  4. Return token + user info                                 │
│  5. Middleware verifica Authorization header                 │
│  6. Extrae claims y autoriza basado en role                  │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│              SQLite Database (data/auth/auth.db)            │
│                                                               │
│  users table:                                                 │
│  ├── id (TEXT PRIMARY KEY)                                   │
│  ├── username (TEXT UNIQUE)                                  │
│  ├── email (TEXT UNIQUE)                                     │
│  ├── hashed_password (TEXT)                                  │
│  ├── role (TEXT: admin, data_manager, user, guest)          │
│  ├── is_active (BOOLEAN)                                     │
│  └── created_at, last_login (TIMESTAMP)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Componentes Principales

### 1. **Módulo de Autenticación** (`src/auth/`)

```
src/auth/
├── __init__.py              # Exports públicos
├── models.py                # Pydantic models (User, Token, etc.)
├── authentication.py        # Gestor JWT + hash passwords
├── middleware.py            # Dependencias FastAPI
└── repository.py            # Gestión de usuarios en BD
```

#### Archivos Clave:

**`authentication.py` - AuthenticationManager**
- `hash_password(password)`: Hash con bcrypt
- `verify_password(plain, hashed)`: Verificación segura
- `create_access_token(user)`: Genera JWT con exp, iat
- `create_refresh_token(user)`: Genera refresh token
- `verify_token(token)`: Decodifica y valida JWT
- `is_token_expired(token)`: Verifica expiración

**`middleware.py` - Dependencias FastAPI**
- `get_current_token()`: Extrae token del header
- `get_current_user()`: Obtiene usuario del token
- `get_current_admin()`: Verifica rol admin
- `get_current_data_manager()`: Verifica rol data_manager
- `require_permission(scope)`: Factory para permisos específicos
- `get_optional_user()`: Usuario opcional (puede ser None)

**`repository.py` - UserRepository**
- `create_user(user_create)`: Crea nuevo usuario
- `get_user_by_id/username/email()`: Obtiene usuario
- `update_last_login(user_id)`: Actualiza timestamp
- `list_users(skip, limit)`: Paginación
- `deactivate_user(user_id)`: Soft delete
- `delete_user(user_id)`: Hard delete

### 2. **Rutas de Autenticación** (`src/service/auth_routes.py`)

```
POST   /auth/register      → Crear cuenta
POST   /auth/login         → Login
POST   /auth/refresh       → Refrescar token
GET    /auth/me            → Info del usuario actual
```

### 3. **Rutas de Gestión de Usuarios** (`src/service/user_routes.py`)

Endpoints para administradores (requieren `get_current_admin`):

```
GET    /users              → Listar usuarios (paginado)
POST   /users              → Crear usuario
GET    /users/{user_id}    → Obtener usuario
PUT    /users/{user_id}/role   → Cambiar rol
DELETE /users/{user_id}    → Desactivar usuario
```

### 4. **Interfaz de Login Streamlit** (`src/ui/auth.py`)

```python
AuthManager
├── is_authenticated()          # Verifica si hay token
├── get_current_user()          # Obtiene user del state
├── get_token()                 # Obtiene token JWT
├── login(username, password)   # POST /auth/login
├── register(...)               # POST /auth/register
├── logout()                    # Limpia session_state
└── get_headers()               # Headers con Authorization

render_login_page()             # UI de login/registro
require_auth()                  # Decorator para páginas protegidas
render_user_menu()              # Menú con logout
```

---

## Flujos de Usuario

### Flujo 1: Registro (Sign Up)

```
Usuario → Clic "Crear cuenta"
   ↓
Formulario: username, email, password, full_name
   ↓
Validar contraseña (≥ 8 caracteres)
   ↓
POST /auth/register
   ↓
Backend:
  1. Verificar username/email no existan
  2. Hash password con bcrypt
  3. Crear usuario en BD con role=USER
  4. Return UserResponse (sin password)
   ↓
Frontend: "Cuenta creada. Inicia sesión."
```

### Flujo 2: Login

```
Usuario → Clic "Iniciar sesión"
   ↓
Formulario: usuario/email + password
   ↓
POST /auth/login { username, password }
   ↓
Backend:
  1. Buscar usuario por username O email
  2. Verificar password con bcrypt
  3. Verificar is_active = true
  4. Crear access_token (exp = ahora + 30min)
  5. Actualizar last_login
  6. Return TokenResponse
   ↓
Frontend:
  1. Guardar token en st.session_state
  2. Guardar user info
  3. st.rerun() → reload página
   ↓
Usuario ve interfaz protegida + menú con nombre
```

### Flujo 3: Logout

```
Usuario → Clic "Cerrar sesión"
   ↓
Frontend:
  1. Limpiar session_state[access_token]
  2. Limpiar session_state[user]
  3. st.rerun() → vuelve a login
   ↓
Usuario ve formulario de login nuevamente
```

### Flujo 4: Request Autenticado

```
Usuario autenticado → Clic "Consultar"
   ↓
Frontend prepara request:
  {
    "question": "¿Cuál es el flujo...?",
    "metadata_filters": {...}
  }
   ↓
Agrega header:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ↓
POST /ask con header Authorization
   ↓
Backend:
  1. HTTPBearer extrae token del header
  2. verify_token(token) → TokenPayload
  3. Obtener usuario actual de claims
  4. Procesar query
  5. Guardar user_id en analytics
   ↓
Respuesta normal con referencias
```

### Flujo 5: Acceso a Admin Dashboard

```
Usuario → Accede a /admin
   ↓
Frontend require_auth():
  1. ¿Hay token? NO → Mostrar login
  2. ¿Hay token? SÍ → Continuar
   ↓
Frontend verifica role:
  1. user["role"] == "admin"? SÍ → Mostrar panel
  2. user["role"] != "admin"? → st.error + st.stop()
   ↓
Admin ve:
  • Gestión de documentos
  • Gestión de feedback
  • Estadísticas
  • Opción de logout
```

---

## Gestión de Tokens

### Access Token

```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user-id-uuid",           // subject (user_id)
    "username": "juan.perez",        // nombre de usuario
    "role": "data_manager",          // admin|data_manager|user|guest
    "iat": 1731664800,               // issued at (Unix timestamp)
    "exp": 1731666600                // expiration (iat + 30 min)
  },
  "signature": "..."                 // HMAC(header + payload, SECRET_KEY)
}
```

**Características:**
- ✅ Duración: 30 minutos (configurable en `.env`)
- ✅ Algoritmo: HS256 (symmetric key)
- ✅ Contiene: user_id, username, role
- ✅ No se revoca: se espera que expire naturalmente
- ❌ No cacheable: cada request necesita validación

### Refresh Token

```json
{
  "payload": {
    "sub": "user-id-uuid",
    "type": "refresh",
    "iat": 1731664800,
    "exp": 1739440800                // 7 días después
  }
}
```

**Uso:**
```
POST /auth/refresh
{
  "refresh_token": "eyJhbGc..."
}
↓
Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

---

## Roles y Permisos

### Matriz RBAC

| Rol | Permisos | Caso de Uso |
|-----|----------|-----------|
| **admin** | Todos | Administrador del sistema |
| **data_manager** | Consultas, documentos, analytics, admin:read | Gestor de conocimiento |
| **user** | Consultas, documentos, analytics | Usuario regular |
| **guest** | Consultas, documentos | Solo lectura |

### Permisos Disponibles

```python
PermissionScope:
  QUERY_READ             # Consultar el RAG
  QUERY_WRITE            # (reserved)
  DOCUMENT_READ          # Listar documentos
  DOCUMENT_WRITE         # Subir/crear documentos
  DOCUMENT_DELETE        # Eliminar documentos
  ANALYTICS_READ         # Ver métricas
  ANALYTICS_WRITE        # (reserved)
  ADMIN_READ             # Acceder a admin panel
  ADMIN_WRITE            # Crear/editar usuarios
  ADMIN_DELETE           # Eliminar usuarios
  USER_READ              # Listar usuarios (admin)
  USER_WRITE             # Modificar usuarios
  USER_DELETE            # Eliminar usuarios
```

### Cómo Proteger un Endpoint

```python
# Requerir autenticación
@app.get("/analytics")
def get_analytics(
    current_user: dict = Depends(get_current_user)
) -> AnalyticsResponse:
    # user_id: str, username: str, role: UserRole

# Requerir admin
@app.get("/admin/users")
def list_users(
    current_admin: dict = Depends(get_current_admin)
) -> list[UserResponse]:
    # Solo admins

# Requerir permiso específico
@app.post("/documents")
def upload(
    current_user: dict = Depends(require_permission(PermissionScope.DOCUMENT_WRITE))
) -> DocumentResponse:
    # Solo usuarios con permiso DOCUMENT_WRITE
```

---

## Configuración

### Variables de Entorno (`.env`)

```bash
# ⚠️ CRÍTICO - Cambiar en PRODUCCIÓN
SECRET_KEY=dev-secret-key-change-in-production

# Tokens (en minutos)
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_MINUTES=10080    # 7 días

# Base de datos
AUTH_DB_PATH=data/auth/auth.db
```

### Generar SECRET_KEY Seguro

```bash
# En Python:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# En Bash:
head -c 32 /dev/urandom | base64
```

### Estructura de Base de Datos

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL,      -- admin|data_manager|user|guest
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login TEXT,
    created_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

---

## Guía de Uso

### Para Desarrolladores

#### Proteger un Endpoint

```python
from src.auth import get_current_user, get_current_admin, require_permission

# Opción 1: Requerir cualquier usuario autenticado
@app.get("/api/data")
def get_data(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    username = current_user["username"]
    role = current_user["role"]
    return {...}

# Opción 2: Requerir admin
@app.post("/api/admin")
def admin_action(current_admin: dict = Depends(get_current_admin)):
    return {...}

# Opción 3: Requerir permiso específico
@app.post("/api/documents")
def upload(
    current_user: dict = Depends(require_permission(PermissionScope.DOCUMENT_WRITE))
):
    return {...}
```

#### Crear Usuario Inicialmente (Admin)

```python
from src.auth.repository import get_user_repository
from src.auth.models import UserCreate, UserRole

user_repo = get_user_repository()

# Crear primer admin
admin = user_repo.create_user(
    UserCreate(
        username="admin",
        email="admin@example.com",
        password="ChangeMe123!",
        full_name="Administrador",
        role=UserRole.ADMIN
    )
)
```

#### En Streamlit

```python
from src.ui.auth import require_auth, render_user_menu, AuthManager

# Proteger página
st.set_page_config(...)
user = require_auth()  # Redirige a login si no está autenticado

st.title("Mi Página Protegida")
render_user_menu()  # Mostrar menú con nombre y logout

# Hacer requests autenticados
headers = AuthManager.get_headers()
response = requests.get(
    f"{API_BASE_URL}/api/data",
    headers=headers
)
```

### Para Usuarios

1. **Crear cuenta:**
   - Clic en "Crear cuenta"
   - Ingresar username, email, password, nombre
   - Clic "Crear cuenta"

2. **Iniciar sesión:**
   - Ingresar email/username y contraseña
   - Clic "Iniciar sesión"
   - Serás redirigido a la app

3. **Cerrar sesión:**
   - Clic en tu nombre en la esquina superior derecha
   - Clic "Cerrar sesión"

---

## Seguridad

### ✅ Implementado

- [x] **Hashing:** bcrypt (12 rounds) para passwords
- [x] **Token:** JWT HS256 con secret key
- [x] **Expiration:** Tokens con expiración (30 min default)
- [x] **RBAC:** 4 roles con permisos granulares
- [x] **Validation:** Pydantic models + type hints
- [x] **SQLite:** BD local segura
- [x] **Protección:** Headers Authorization en requests

### ⚠️ A Implementar (Sesión 3: RS4, RS5)

- [ ] **HTTPS/TLS:** SSL certificates en producción
- [ ] **Cifrado:** Datos en reposo (Fernet)
- [ ] **GDPR:** PII detection + masking
- [ ] **Auditoría:** Logging de acciones de usuario
- [ ] **Rate Limiting:** Prevenir brute force

### Buenas Prácticas

1. **Nunca** expongas el `hashed_password` en respuestas
2. **Siempre** usa HTTPS en producción
3. **Cambiar** SECRET_KEY en cada ambiente
4. **Rotar** tokens en background (refresh)
5. **Validar** input en todos los endpoints
6. **Loguear** intentos de login fallidos
7. **Desactivar** usuarios en lugar de eliminar

### Escenarios de Riesgo

| Riesgo | Mitigación |
|--------|-----------|
| Token robado | Token corta duración (30 min), HTTPS |
| Brute force | Rate limiting, intents limit |
| SQLi | Usar ORM/parameterized queries (sqlite3 prepared) |
| CSRF | Framework maneja (no aplica a API) |
| XSS | Streamlit sanitiza, no eval |
| Session fixation | Token único por usuario+time |

---

## Preguntas Frecuentes

**¿Cómo agrego autenticación a Streamlit?**
```python
user = require_auth()  # Eso es todo!
```

**¿Cómo protejo un endpoint FastAPI?**
```python
@app.get("/data")
def get_data(current_user: dict = Depends(get_current_user)):
    ...
```

**¿Cómo cambio el rol de un usuario?**
```bash
curl -X PUT http://localhost:8000/users/{user_id}/role \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"new_role": "admin"}'
```

**¿Cómo creo usuarios vía API?**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "juan",
    "email": "juan@example.com",
    "password": "SecurePass123",
    "full_name": "Juan Pérez"
  }'
```

**¿Qué pasa si mi token expira?**
Obtendrás error 401. Usa `/auth/refresh` con tu refresh token para obtener uno nuevo.

---

## Próximas Mejoras

- [ ] Sesión 3: Cifrado HTTPS + en reposo (RS4)
- [ ] Sesión 4: GDPR + PII masking (RS5)
- [ ] Sesión 6: Logging centralizado (RM2)
- [ ] Two-factor authentication (2FA)
- [ ] OAuth2 integration (Google, GitHub)
- [ ] API keys para integraciones
- [ ] Audit trail completo

---

**Documento generado:** 2025-11-15
**Versión:** 1.0
**Siguiente revisión:** Después de implementar RS4 (Cifrado)
