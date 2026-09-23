# SyncTune

Plataforma para conectar YouTube y Spotify: importar, comparar y sincronizar
canciones y playlists entre ambos servicios.

**Estado actual**: podés importar una **canción** (flujo principal) o una
**playlist completa** (hasta 50 canciones) de YouTube a Spotify, de punta a
punta, con preview, nivel de confianza, detección de duplicados,
confirmación explícita e historial. Además: conexión con YouTube vía OAuth
de Google, un Centro de Conexiones, un Dashboard con estadísticas reales, y
herramientas de playlist (comparar, detectar duplicados, fusionar). Tema
claro/oscuro/sistema y command palette (Ctrl+K). Ver
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) y
[docs/EVOLUTION_PLAN.md](docs/EVOLUTION_PLAN.md) para el detalle fase por
fase. Sincronización automática/bidireccional y jobs en background
quedaron pospuestos deliberadamente (ver esos documentos) — no hay
infraestructura de jobs ni una política de conflictos definida todavía.

## ⚠️ Limitación importante de Spotify (léela antes de probar)

Desde febrero/marzo de 2026, Spotify exige que la cuenta dueña de la app de
desarrollo tenga **Premium**, y limita las apps en Development Mode a
**5 usuarios**, que hay que agregar a mano en el dashboard de Spotify
(**App Settings → User Management**). Alcanzar el modo "Extended Quota" (sin
ese límite) requiere ser una empresa registrada con 250k usuarios activos —
fuera del alcance de un proyecto personal. Ver detalles y fuentes en
`IMPLEMENTATION_PLAN.md`.

## Arquitectura

```
React (frontend)
      ↓
FastAPI (backend)
      ↓
Services (spotify_service, youtube_service, matching_service, sync_service,
          playlist_service, track_identity_service, analytics_service)
      ↓
Spotify Web API / YouTube Data API v3        PostgreSQL
```

El frontend nunca habla directamente con Spotify o YouTube para operaciones
que requieran tokens — todo pasa por el backend. Los tokens se guardan
cifrados en la base de datos, nunca en la cookie de sesión ni en el
frontend.

## Estructura

```
backend/
├── app/
│   ├── main.py              # arma la app, monta middlewares y routers
│   ├── api/                  # endpoints HTTP (sin lógica de negocio)
│   │   ├── spotify.py         # OAuth, perfil, playlists
│   │   ├── youtube.py         # OAuth de Google (login/callback/status/disconnect)
│   │   ├── sync.py            # preview / confirmar / historial (canción y playlist)
│   │   ├── dashboard.py       # estadísticas + actividad reciente
│   │   └── playlists.py       # comparar / salud (duplicados) / fusionar
│   ├── services/              # toda la comunicación con APIs externas + lógica
│   │   ├── spotify_service.py
│   │   ├── youtube_service.py       # video/playlist lookup (API key) + OAuth (Google)
│   │   ├── matching_service.py      # limpieza de título + scoring de confianza
│   │   ├── sync_service.py          # orquesta youtube+spotify+matching, persiste
│   │   ├── track_identity_service.py # "¿son la misma canción?" (comparador, duplicados)
│   │   ├── playlist_service.py      # comparar/salud/fusionar playlists
│   │   └── analytics_service.py     # agregados de syncs/sync_items para el dashboard
│   ├── models/                 # tablas SQLAlchemy
│   │   ├── user.py, connection.py, sync.py, sync_item.py
│   ├── schemas/                # modelos Pydantic de request/response
│   ├── core/
│   │   ├── config.py           # Settings (variables de entorno)
│   │   ├── database.py         # engine/sesión SQLAlchemy
│   │   ├── security.py         # ciclo de vida de tokens (Spotify + YouTube)
│   │   ├── crypto.py           # cifrado de tokens en reposo
│   │   └── logging.py          # eventos nombrados, nunca con secretos
│   └── tests/                  # pytest (unit + integración contra Postgres + API/TestClient)
├── migrations/                 # Alembic
├── Dockerfile
└── requirements.txt

frontend/
├── src/
│   ├── pages/Home.tsx           # Centro de Importación: selector Canción/Playlist
│   ├── pages/SongImport.tsx     # flujo de una canción
│   ├── pages/PlaylistImport.tsx # flujo de una playlist completa
│   ├── pages/History.tsx        # historial
│   ├── pages/Connections.tsx    # Centro de Conexiones (Spotify + YouTube)
│   ├── pages/Dashboard.tsx      # estadísticas + actividad reciente
│   ├── pages/PlaylistTools.tsx  # comparar / salud / fusionar
│   ├── pages/CommandPalette.tsx # Ctrl+K
│   ├── format.ts                # helpers compartidos (fechas, labels, errores)
│   └── api.ts, types.ts
└── Dockerfile, nginx.conf

docker-compose.yml               # Postgres + backend + frontend
.github/workflows/ci.yml         # tests de backend + build de frontend
```

`api/auth.py`, `api/users.py` del layout original del spec todavía no
existen: se agregan cuando haya funcionalidad real que los necesite
(Regla 3: no crear código o carpetas sin uso). El OAuth de Spotify ya
cumple el rol que tendría `api/auth.py`.

## 1. Credenciales

### Spotify
1. [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → **Create app**, con una cuenta **Premium**.
2. Redirect URI: `http://127.0.0.1:8000/api/spotify/callback`
3. Copiá **Client ID** y **Client Secret** desde Settings.
4. En **User Management**, agregá cada cuenta de Spotify que vaya a probar la app (máx. 5).

### YouTube Data API
1. [console.cloud.google.com](https://console.cloud.google.com/) → creá/elegí un proyecto.
2. **APIs & Services → Library** → habilitá "YouTube Data API v3".
3. **APIs & Services → Credentials** → **Create Credentials → API Key**.

### Google OAuth (opcional — solo para "Conectar YouTube")
El resto de la app funciona sin esto (Spotify + búsqueda de videos siguen
andando con la API key de arriba). Pasos si querés probar la conexión con
YouTube:
1. **APIs & Services → OAuth consent screen** → External → **Testing** (es
   la única opción viable para un proyecto personal — ver
   `docs/EVOLUTION_PLAN.md`). Agregá tu cuenta de Google como test user.
2. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   → Web application.
3. Redirect URI: `http://127.0.0.1:8000/api/youtube/callback`
4. Mientras la app no esté verificada por Google, hay que reconectar cada
   7 días (el token expira) — limitación conocida y aceptada.

## Opción A — Desarrollo local (recomendado para iterar)

### 1. Base de datos
```bash
docker compose up -d postgres
```
Publica Postgres en el puerto **5434** del host (no 5432 — evita chocar con
una instalación nativa de PostgreSQL que ya pueda existir en la máquina).

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Completá `.env` con tus credenciales. Para `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Aplicar las migraciones y levantar el servidor:
```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```
Docs interactivas (OpenAPI): `http://127.0.0.1:8000/docs`.

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
Abrí `http://127.0.0.1:5173`.

## Opción B — Todo con Docker Compose

Con `backend/.env` ya creado (paso anterior):
```bash
docker compose up -d --build
```
Levanta Postgres + backend (corre `alembic upgrade head` solo al arrancar)
+ frontend (build de producción de Vite servido por nginx) —
`http://127.0.0.1:5173`. Verificado end-to-end: build, migración y
frontend↔backend↔Postgres funcionando juntos.

## Flujo actual

En `/` elegís **🎵 Canción** o **📋 Playlist**.

**Canción** (flujo principal):
1. Conectás tu cuenta de Spotify (OAuth) — se crea tu usuario en la base de
   datos la primera vez.
2. Pegás una URL de YouTube.
3. El backend limpia el título del video (saca "(Official Video)", "Lyrics",
   "Remastered", "[Sub Español]", etc. — sin depender del canal, para que
   funcione igual con reuploads/subtítulos) y busca coincidencias en Spotify,
   sin usar `search.list` de YouTube para no gastar cuota innecesariamente.
4. Cada candidato muestra un % de confianza (artista + título + duración +
   versión — live/acoustic/remix/remastered/etc.).
5. Elegís el track correcto y una playlist (existente o nueva).
6. Confirmás explícitamente — recién ahí se modifica Spotify. Si la canción
   ya estaba en la playlist, se detecta y no se duplica.
7. La operación queda en `/history`, con su resultado.

**Playlist** (requiere conectar YouTube en `/connections` — OAuth de
Google, lee incluso playlists privadas):
1. Pegás una URL de playlist de YouTube.
2. Se procesan hasta 50 canciones (más grande, se trunca con aviso —
   playlists más largas necesitan jobs en background, todavía no
   implementado).
3. Por cada canción se muestra el mejor candidato de Spotify con su
   confianza; podés cambiarlo por otro candidato o ignorarla.
4. Elegís la playlist destino y confirmás una sola vez para todo el lote —
   duplicados contra la playlist destino se detectan y no se repiten.
5. Igual que con una canción, la operación queda en `/history`.

**Otras secciones**: `/dashboard` (estadísticas reales + actividad
reciente), `/connections` (conectar/desconectar Spotify y YouTube, nunca
tokens), `/playlists` (comparar dos playlists, detectar duplicados dentro
de una — "Playlist Health" —, fusionar varias con opción de evitar
duplicados). **Ctrl+K** abre un command palette para saltar entre
secciones; el ícono de tema en el header cicla Sistema → Claro → Oscuro.

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/spotify/login` | Redirige al OAuth de Spotify |
| GET | `/api/spotify/callback` | Callback de OAuth, crea/vincula el usuario |
| GET | `/api/spotify/me` | Estado de la sesión actual |
| POST | `/api/spotify/logout` | Cierra la sesión (mantiene la conexión guardada) |
| POST | `/api/spotify/disconnect` | Revoca y borra la conexión guardada |
| GET | `/api/spotify/playlists` | Playlists del usuario |
| POST | `/api/spotify/playlists` | Crea una playlist |
| POST | `/api/spotify/playlists/{id}/tracks` | Agrega un track a una playlist |
| GET | `/api/youtube/login` | Redirige al OAuth de Google (requiere sesión de Spotify activa) |
| GET | `/api/youtube/callback` | Callback de OAuth, vincula la conexión al usuario actual |
| GET | `/api/youtube/status` | Estado de la conexión con YouTube |
| POST | `/api/youtube/disconnect` | Borra la conexión guardada |
| POST | `/api/sync/preview` | Analiza un video de YouTube, devuelve candidatos con confianza |
| POST | `/api/sync/{id}/confirm` | Confirma un candidato + playlist, con detección de duplicados |
| POST | `/api/sync/playlist/preview` | Analiza una playlist de YouTube (hasta 50 canciones), candidatos por canción |
| POST | `/api/sync/{id}/playlist/confirm` | Confirma las selecciones del lote + playlist, con detección de duplicados |
| GET | `/api/sync/history` | Historial de sincronizaciones del usuario |
| GET | `/api/sync/{id}` | Detalle de una sincronización |
| GET | `/api/dashboard` | Estadísticas + actividad reciente |
| GET | `/api/playlists/compare` | Compara dos playlists de Spotify (coinciden/solo en A/solo en B) |
| GET | `/api/playlists/{id}/health` | Detecta duplicados dentro de una playlist |
| POST | `/api/playlists/merge/preview` | Vista previa de fusionar N playlists (con o sin dedupe) |
| POST | `/api/playlists/merge/confirm` | Fusiona N playlists en una nueva o existente |

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest app/tests -v
```

Requiere Postgres corriendo (`docker compose up -d postgres`) — algunos
tests insertan filas reales contra la base y las revierten al final (ver
`app/tests/conftest.py`). 76 tests en total: motor de matching (con los
casos de ejemplo del spec), identidad de tracks, parser de URLs (video y
playlist), OAuth de Google, cifrado de tokens, agregados del dashboard, y
un test de seguridad a nivel API (`test_api_auth.py`, con `TestClient` de
FastAPI) que confirma que todo endpoint protegido devuelve 401 sin sesión.
Todavía no hay tests de frontend.

## Docker

`docker-compose.yml` levanta el stack completo (Postgres + backend +
frontend) — ver "Opción B" arriba. `.github/workflows/ci.yml` corre los
tests de backend y el build de frontend en cada push/PR; todavía no puede
ejecutarse porque el proyecto no tiene un remoto de GitHub configurado
(el repo Git local ya existe, `git init`, sin commits todavía).
