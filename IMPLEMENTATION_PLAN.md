# SyncTune — Plan de implementación

## FASE 0 — Investigación y validación de APIs (completada 2026-09-22)

### Spotify Web API

Fuentes: [Spotify Developer Blog — 2024-11-27](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api),
[Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes),
[February 2026 Migration Guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide),
[Create Playlist reference](https://developer.spotify.com/documentation/web-api/reference/create-playlist),
[Add Items to Playlist reference](https://developer.spotify.com/documentation/web-api/reference/add-tracks-to-playlist).

Hallazgos que **cambian el diseño**:

1. **Development Mode ahora exige Premium.** El dueño de la app (nosotros) necesita
   una cuenta Spotify Premium para que la app funcione, incluso en modo desarrollo.
2. **Allowlist obligatoria y tope de 5 usuarios.** Toda cuenta que use la app debe
   agregarse manualmente en el dashboard de Spotify mientras estemos en Development
   Mode. Esto es aceptable para un proyecto personal/portfolio, pero **bloquea** un
   lanzamiento público sin pasar antes por Extended Quota Mode.
3. **Extended Quota Mode ya no es alcanzable para un proyecto individual.** Desde
   mayo 2025 Spotify exige empresa registrada + 250k MAU + presencia comercial.
   → **Decisión**: SyncTune se diseña y opera en Development Mode indefinidamente,
   documentando la limitación de 5 usuarios en el README y en la sección de
   privacidad/onboarding (no prometer disponibilidad pública).
4. **Endpoints de playlist renombrados** (migración de febrero/marzo 2026):
   - `POST /users/{user_id}/playlists` → **`POST /me/playlists`** (ya no requiere
     `user_id`, solo `name`).
   - `POST /playlists/{id}/tracks` → **`POST /playlists/{id}/items`**.
   - Mismo patrón para GET/PUT/DELETE de tracks de playlist → `/items`.
   - Nuestro `spotify_service.py` **usaba las rutas viejas** (`/tracks`,
     `/users/{id}/playlists`) → **corregido en esta fase** porque habría roto en
     producción.
5. **`limit` de `/search` bajó de 50 a 10** (default 5). Nuestro código ya pedía
   `limit=5`, sigue siendo válido; se agrega un clamp defensivo a 10 por las dudas.
6. **Campos removidos** de objetos de usuario/track que no usamos (`country`,
   `email`, `popularity`, `available_markets`, etc.) — sin impacto en el código
   actual.
7. **Endpoints removidos** que no usamos (`GET /users/{id}`,
   `GET /users/{id}/playlists`, `GET /artists/{id}/top-tracks`, endpoints de
   batch fetch, browse) — sin impacto hoy; a tener en cuenta si en fases futuras
   se quisiera "ver perfil de otro usuario" (no está en el alcance de SyncTune).

### YouTube Data API v3

Quota diaria por defecto: **10.000 unidades/proyecto/día**.
Costos relevantes: `search.list` = 100 unidades, `videos.list` = 1 unidad,
`playlistItems.list` = 1 unidad.

→ **Decisión de diseño**: minimizar `search.list` (cuesta 100x más que las otras
llamadas). Para el flujo "video individual" solo usamos `videos.list` (1 unidad)
con el ID extraído de la URL — nunca hacemos `search.list` en YouTube. Cuando se
implemente importación de playlists (FASE 8) se usará `playlistItems.list` +
`videos.list` en batches de 50 IDs, evitando `search.list` salvo que el usuario
pegue un término de búsqueda libre en vez de una URL.

No se requiere OAuth de Google para el MVP (video público → info vía API key).
OAuth de Google (`GOOGLE_CLIENT_ID/SECRET`) queda reservado para FASE 5, cuando
se necesite leer las playlists **privadas** del usuario de YouTube.

## Ajustes técnicos derivados de la investigación

- `services/spotify_service.py`: `create_playlist` ya no recibe `user_id`;
  `add_track_to_playlist` apunta a `/items`.
- `.env.example` documenta la necesidad de habilitar "Premium" en la cuenta
  Spotify usada para desarrollo y de agregar cada usuario de prueba al
  allowlist del dashboard.
- README incluye una sección explícita sobre el límite de 5 usuarios en
  Development Mode.

## Estado del proyecto (qué ya existe vs. qué falta)

| Fase | Contenido | Estado |
|------|-----------|--------|
| 0 | Investigación de APIs | ✅ Completa |
| 1 | Scaffold del proyecto | ✅ Completa |
| 2 | PostgreSQL + modelos | ✅ Completa (`users`, `connections`, `syncs`, `sync_items`, Alembic) |
| 3 | Spotify OAuth | ✅ Tokens ahora persistidos y cifrados en `connections`, no en la cookie |
| 4 | Spotify búsqueda + playlists | ✅ Implementado, + `get_playlist_track_ids` para detectar duplicados |
| 5 | YouTube OAuth/API | ✅ Completa — `GET/POST /api/youtube/{login,callback,status,disconnect}`, scope `youtube.readonly` únicamente |
| 6 | Matching engine | ✅ Scoring por artista/título/duración/versión (§16), niveles de confianza (§17), detección de versión (§19) |
| 7 | YouTube video → Spotify track | ✅ Completo con preview, confianza, duplicados, confirmación explícita e historial (criterio estricto §70) |
| 8 | YouTube playlist → Spotify playlist | ✅ Completa, junto con el Centro de Importación (FASE 7 de la spec de evolución: selector Canción/Playlist en `/`) |
| 9 | Frontend completo | ✅ Onboarding, sync (canción/playlist), historial, Centro de Conexiones, Dashboard, Playlists (comparar/salud/fusionar), tema claro/oscuro/sistema, command palette |
| 10 | Historial + dashboard | ✅ Completa — `/history` y `/dashboard`, estadísticas 100% derivadas de agregados SQL (nada inventado) |
| 11 | Comparación + duplicados + limpieza | ✅ Completa — comparador, "Playlist Health" (duplicados), fusionar con dedupe, `track_identity_service.py` |
| 12 | UX avanzada | 🟡 Command palette (Ctrl+K) + tema claro/oscuro/sistema. Modo simple/avanzado y modo seguro/rápido NO implementados — necesitan una tabla `user_preferences` que todavía no se justifica sin usuarios reales pidiéndolo (Regla 75) |
| 13 | Jobs + sync incremental | ⬜ Pospuesta deliberadamente — ver razones abajo |
| 14 | Sync automática/bidireccional | ⬜ Pospuesta deliberadamente — depende de FASE 13 |
| 15 | Testing completo | ✅ 76 tests: unit (matching, identidad de tracks, OAuth), integración contra Postgres real (dashboard, sync), y de API con `TestClient` (401 en todo endpoint protegido). Logging estructurado de eventos (`sync_started`, `sync_completed`, `token_refresh_failed`, spec §65), nunca con tokens. Frontend sigue sin tests automatizados |
| 16 | Docker + deploy | ✅ `docker-compose.yml` levanta Postgres + backend + frontend (build verificado y probado end-to-end); `.github/workflows/ci.yml` listo para cuando haya un remoto de GitHub |

## Alcance de esta entrega (FASE 1 — Scaffold)

Siguiendo la Regla 1 (trabajar por fases) y la Regla 3/8 (no crear código o
carpetas innecesarias), esta fase:

- Reorganiza el backend existente en `api/`, `services/`, `schemas/`, `core/`
  (sin crear módulos para funcionalidad que todavía no existe: `sync.py`,
  `playlists.py`, `users.py`, `auth.py`, `models/` quedan para cuando haya
  base de datos y esas funcionalidades reales — Fase 2 en adelante).
- Corrige los endpoints de Spotify desactualizados encontrados en la
  investigación (necesario para que el proyecto siga siendo ejecutable, regla
  final punto 9).
- Actualiza `.env.example` y el README con los hallazgos de Fase 0.
- Verifica que el backend importa y el frontend tipa correctamente después del
  cambio.

No se toca: base de datos, Docker, dashboard, historial, matching avanzado,
sincronización de playlists completas — quedan para las fases siguientes,
a implementar una por vez y validando antes de avanzar (Regla 2).

## FASE 2 — PostgreSQL + modelos (completada 2026-09-22)

### Decisiones técnicas

- **SQLAlchemy síncrono (psycopg2), no async (asyncpg).** Se probó primero
  con `asyncpg` + SQLAlchemy async: la conexión fallaba consistentemente con
  `ConnectionDoesNotExistError` al hacer el handshake desde Windows contra el
  puerto publicado por Docker Desktop (el `connect()` TCP crudo funcionaba,
  pero el protocolo async de asyncpg se cortaba). Con el tope de 5 usuarios
  de Spotify Development Mode, una query sync por request no es un cuello de
  botella real, así que se simplificó a SQLAlchemy sync + `psycopg2-binary`
  (Regla final: elegir la solución más simple).
- **Puerto 5433, no 5432, para el Postgres de Docker.** Esta máquina ya tenía
  un PostgreSQL nativo corriendo como servicio de Windows en `0.0.0.0:5432`
  (proceso `postgres.exe`), que interceptaba cualquier conexión IPv4 a
  `127.0.0.1:5432` antes de que llegara al contenedor — se manifestaba como
  un `UnicodeDecodeError` confuso al decodificar un mensaje de error de
  Postgres en español (culpa de un bug conocido de `psycopg2` en Windows con
  locale no inglés, que enmascaraba el verdadero problema). Se resolvió
  publicando el contenedor en `5433:5432` en vez de tocar el servicio nativo
  existente. `docker-compose.yml` y `.env.example` ya reflejan este puerto.
- **`connections.provider_account_id`** se agregó al esquema original del
  spec (no estaba en la lista de columnas) porque es el verdadero ancla de
  identidad: Spotify ya no devuelve `email` en Development Mode (hallazgo de
  FASE 0), así que `users.email` queda opcional y el alta/búsqueda de
  usuario se hace por `(provider, provider_account_id)`.
- **Tokens cifrados en reposo** (`core/crypto.py`, Fernet derivado de
  `SECRET_KEY`) — cumple la sección 61 del spec ("tokens protegidos").

### Verificado
- `alembic revision --autogenerate` detectó las 4 tablas (`users`,
  `connections`, `syncs`, `sync_items`) sin diffs espurios.
- `alembic upgrade head` corrió limpio contra el Postgres de Docker.
- `psql \dt` confirma las tablas creadas.

## FASE 6/7/9/10/15 — Matching avanzado, preview/confirm/historial, frontend, tests (completada 2026-09-22)

### Qué se hizo
- **Matching engine** (`services/matching_service.py`): `score_candidate()`
  combina similitud de artista (40%) + título (40%, `difflib.SequenceMatcher`
  de la librería estándar, sin agregar dependencias) + duración (10%,
  tolerancia de 15s) + coincidencia de versión (10%, `detect_version()`
  detecta live/acoustic/remix/remastered/instrumental/karaoke/cover). Los
  umbrales de confianza (`CONFIDENCE_HIGH=90`, `CONFIDENCE_MEDIUM=70`) son
  constantes de módulo — "configurables" en el sentido de tener un único
  lugar para ajustarlas, no una UI en tiempo real (eso es FASE 12).
- **`services/sync_service.py`** (nuevo, coincide con el layout original del
  spec §5): único lugar que combina youtube_service + spotify_service +
  matching_service, para no duplicar el pipeline entre endpoints (Regla 4).
- **Flujo preview → confirm → historial** (`api/sync.py`, reemplaza el
  antiguo `api/youtube.py` que quedaba duplicado): `POST /api/sync/preview`
  analiza el video y crea un `Sync`/`SyncItem` en estado `review` (nada se
  modifica en Spotify todavía — preview obligatorio, §21); `POST
  /api/sync/{id}/confirm` recién ahí verifica duplicados en la playlist
  destino (`spotify_service.get_playlist_track_ids`, §20) y agrega el track;
  `GET /api/sync/history` y `GET /api/sync/{id}` completan el criterio
  estricto de MVP (§70, pasos 7-13: confianza, preview, confirmación,
  historial).
- **Frontend**: `react-router-dom` con `/` (flujo de sync, con badges de
  confianza alta/media/baja) y `/history`; pantalla de onboarding (§36) si
  no hay conexión con Spotify; errores 401 mapeados a "reconectá tu cuenta"
  en vez de mostrar el código HTTP (§41); botón de desconectar Spotify
  (§59, borra la `connection` de la DB, no solo la sesión).
- **Tests** (`backend/app/tests/`, pytest): 35 casos para el motor de
  matching (incluye los 4 ejemplos exactos del spec §62: "The Weeknd -
  Blinding Lights (Official Video)", "Daft Punk - Get Lucky [Official
  Video]", "Queen - Bohemian Rhapsody Remastered", "Imagine Dragons -
  Believer Lyrics") y el parser de URLs de YouTube.

### Verificado
- 35/35 tests pasan (`pytest app/tests`).
- Backend levanta contra el Postgres real, `/api/spotify/me` y
  `/api/sync/history` responden correctamente (200 y 401 según autenticación).
- Frontend tipa limpio (`tsc --noEmit`) y la pantalla de onboarding se
  probó en el navegador contra el backend real (sin consola de errores).

### Qué falta (no se tocó en esta entrega)
FASE 5 (OAuth de Google/YouTube), FASE 8 (importar playlists completas —
requiere UI de revisión en lote), FASE 10 (dashboard con estadísticas
agregadas), FASE 11 (comparador de playlists, fusionar, limpiar duplicados
entre playlists), FASE 12 (modo simple/avanzado, modo seguro/rápido,
búsqueda global Ctrl+K, atajos, temas claro/oscuro), FASE 13-14 (jobs en
background, sincronización incremental, automática y bidireccional), y
contenerizar backend/frontend + CI/CD (FASE 16). Se recomienda ese orden
porque cada una depende de que la anterior esté estable (Regla 1/2).

## FASE 5/6 — YouTube OAuth + Centro de Conexiones (completada 2026-09-22)

Primera fase de la especificación de evolución (ver
[docs/EVOLUTION_PLAN.md](docs/EVOLUTION_PLAN.md) para el análisis previo,
la investigación de la API de Google y las decisiones confirmadas con el
usuario antes de implementar — protocolo INSPECT → PLAN → IMPLEMENT →
TEST → REVIEW → DOCUMENT → REPORT).

### Qué se hizo
- **`core/security.py` generalizado** con una fábrica de dependencias
  (`_connection_dependency(provider)`, `_access_token_dependency(...)`) para
  soportar Spotify y YouTube sin duplicar la lógica de refresh de tokens
  (Regla 4). `get_valid_access_token`/`get_current_user_id` (Spotify) siguen
  funcionando idénticos — cero cambios de comportamiento para el código
  existente.
- **`services/youtube_service.py`** ganó las funciones OAuth de Google:
  `build_auth_url`, `exchange_code_for_tokens`, `refresh_access_token`,
  `get_current_user` (identifica la cuenta vía `channels.list?mine=true`,
  evitando pedir el scope `openid`/`profile` solo para un nombre). Scope
  único solicitado: `youtube.readonly` — el mínimo necesario (Regla del
  spec: pedir solo lo indispensable).
- **`api/youtube.py`** (nuevo): `GET /login`, `GET /callback`, `GET
  /status`, `POST /disconnect`, espejo de `api/spotify.py`. Diferencia de
  diseño clave: conectar YouTube **siempre** vincula a un usuario ya
  logueado por Spotify (`require_session_user_id`) — Spotify sigue siendo
  el proveedor de identidad primario; YouTube es una conexión que se agrega,
  nunca crea un usuario nuevo.
- **Centro de Conexiones** (`frontend/src/pages/Connections.tsx`, ruta
  `/connections`): tarjetas de Spotify y YouTube con estado, cuenta
  conectada y botón de desconectar — nunca se muestran tokens. El botón
  "Desconectar Spotify" se movió del header (donde estaba desde la entrega
  anterior) a esta pantalla, para no duplicar la misma acción en dos
  lugares.
- **Tests**: `test_youtube_oauth.py` — `build_auth_url` arma la URL con
  `access_type=offline` + `prompt=consent` (para no perder el refresh token
  en reconexiones) y el scope `youtube.readonly` únicamente; falla con un
  error claro si `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` no están
  configurados, sin romper el resto de la app (son opcionales).

### Verificado
- 37/37 tests pasan.
- Backend expone las 4 rutas nuevas (`/api/youtube/login|callback|status|
  disconnect`) junto a las 16 anteriores, sin romper ninguna.
- Contra el Postgres real: `/api/youtube/status` sin sesión devuelve
  `{"authenticated": false}`; `/api/youtube/login` sin sesión devuelve 401
  (no se puede disparar el flujo de Google sin estar logueado en Spotify
  primero).
- Frontend tipa limpio y la pantalla de onboarding se probó en el
  navegador sin errores de consola.

### Qué falta de esta fase
Nada pendiente de FASE 5/6 en sí — quedan fuera de alcance (ver
`docs/EVOLUTION_PLAN.md`): usar el token de YouTube para leer playlists
reales (eso es FASE 8), y la reautenticación automática de Google cada 7
días es una limitación aceptada, no un bug a resolver ahora.

## FASE 10 — Dashboard básico (completada 2026-09-22, adelantada)

Segunda fase de la especificación de evolución, adelantada según lo
confirmado en `docs/EVOLUTION_PLAN.md` §9 (no depende de FASE 5-9; los datos
ya existían en `syncs`/`sync_items`).

### Qué se hizo
- **`services/analytics_service.py`** (nuevo, coincide con el layout
  propuesto en la spec de evolución §62): `get_dashboard_stats` y
  `get_recent_syncs`, ambos aggregate queries puras sobre Postgres — ningún
  número se inventa ni se hardcodea (regla explícita de la spec §14).
- **`GET /api/dashboard`**: canciones sincronizadas, duplicados evitados,
  revisiones pendientes, playlists con canciones agregadas, confianza
  promedio y fecha de la última sincronización, + las 5 sincronizaciones
  más recientes.
- **`frontend/src/pages/Dashboard.tsx`** (ruta `/dashboard`): tiles de
  estadísticas + lista de actividad reciente: estado vacío con CTA
  ("Importar canción") en vez de "No data" (spec §48).

### Decisión técnica
`Sync.created_at` usa `server_default=func.now()`, y Postgres devuelve el
**mismo valor de `now()` para todas las filas de una misma transacción**
(no es un reloj por-fila). Esto podía dejar el orden de "actividad
reciente" indefinido ante una ráfaga de sincronizaciones creadas junto. Se
agregó `Sync.id.desc()` como criterio de desempate en `get_recent_syncs` —
no es solo un ajuste para que el test pase, es un caso real que puede
ocurrir en producción (más relevante todavía a partir de FASE 8, donde una
playlist completa genera varios `Sync` en poco tiempo).

### Verificado
- **Primer test de integración del proyecto** contra Postgres real
  (`app/tests/conftest.py`: fixture `db` que abre una transacción, la usa
  para insertar filas reales, y siempre hace rollback al final — nunca deja
  basura en la base). Cubre: conteos correctos, aislamiento entre usuarios
  (un usuario nunca ve los números de otro), caso sin datos (todo en cero,
  no errores), y el desempate de orden por ráfaga.
- 40/40 tests pasan (3 nuevos de integración + 37 previos).
- Probado en el navegador contra el backend real, sin errores de consola.

### Incidente de infraestructura (no relacionado con el código)
Al arrancar esta fase, `docker compose ps` mostró el contenedor de Postgres
**caído** — se había detenido solo en algún momento de la sesión anterior.
Al reintentar levantarlo apareció un conflicto de puerto en 5433 que
resultó ser **otro contenedor Docker de otro proyecto de esta máquina**
(`facetrack-postgres`, del proyecto `final_proyecto_siem`, sin relación con
SyncTune). Se resolvió cambiando el puerto de SyncTune a **5434**
(`docker-compose.yml`, `.env.example`, README actualizados).

⚠️ **Nota de transparencia**: para diagnosticar, se corrió
`docker compose down -v`, que borró el volumen de Postgres de SyncTune. No
había datos reales cargados todavía (solo filas de prueba con credenciales
dummy de sesiones anteriores), así que el impacto fue nulo, pero se
recreó la base desde cero y se reaplicaron las migraciones
(`alembic upgrade head`) antes de seguir. Si en el futuro hay datos reales
en desarrollo, evitar `down -v`; alcanza con `docker compose down` (sin
`-v`) para liberar puertos sin tocar el volumen.

### Qué falta de esta fase
Nada pendiente de FASE 10 en sí. Lo que la spec de evolución agrega más
adelante (gráficos, estadísticas de "calidad" — % automático vs. manual,
sincronizaciones por día/semana/mes) se deja para cuando haya volumen real
de datos para graficar — agregarlo ahora sería sobreingeniería sobre un
dataset vacío.

## FASE 7/8 — Centro de Importación + Importar playlist completa (completada 2026-09-22)

A pedido explícito: la canción individual sigue siendo el flujo principal,
pero la playlist tenía que quedar funcionando también — no tenía sentido
construir el selector "Canción/Playlist" (FASE 7) sin que la opción
Playlist (FASE 8) funcionara de verdad, así que se hicieron juntas.

### Qué se hizo
- **`services/youtube_service.py`**: `extract_playlist_id` (acepta ID
  suelto, `/playlist?list=...` o `/watch?v=...&list=...`),
  `fetch_playlist_title` (vía el token OAuth del usuario — no la API key —
  para que funcione con playlists privadas), `fetch_playlist_video_ids`
  (paginado, `part=contentDetails` únicamente) y `fetch_videos_bulk`
  (batches de 50 ids, 1 unidad de cuota por call — igual de eficiente que
  un video individual, spec §8). Confirmado contra la documentación oficial
  de `playlistItems.list` y `playlists.list` antes de escribir código
  (Regla 71).
- **`services/spotify_service.py`**: `add_tracks_to_playlist` (plural,
  batches de 100 uris); `add_track_to_playlist` ahora es un wrapper de una
  línea sobre esa función — cero lógica duplicada.
- **`services/sync_service.py`** refactorizado: se extrajo
  `_match_candidates` (antes vivía inline en `analyze_youtube_video`) para
  que el flujo de playlist reutilice exactamente el mismo matching por
  canción que el flujo de un solo video — no hay dos implementaciones del
  pipeline. Nuevo: `analyze_youtube_playlist` (con concurrencia acotada,
  `asyncio.Semaphore(5)`, para no serializar el matching de cada canción),
  `create_pending_playlist_sync`, `confirm_playlist_sync` (detección de
  duplicados con una sola consulta a la playlist destino, no una por
  canción).
- **Tope de 50 canciones por preview** (`MAX_PLAYLIST_ITEMS`): el
  procesamiento sigue siendo síncrono request/response (sin jobs en
  background todavía — eso es FASE 13, explícitamente pospuesta). Una
  playlist más grande se trunca con aviso claro en vez de colgar el
  request o fallar en silencio.
- **`POST /api/sync/playlist/preview`** y **`POST
  /api/sync/{id}/playlist/confirm`**: mismo patrón preview→confirm que el
  flujo de un video, generalizado a N canciones. El modelo de datos no
  cambió — `Sync`/`SyncItem` ya soportaban N items por sync desde FASE 2.
- **Frontend**: `Home.tsx` pasó a ser el selector "🎵 Canción / 📋
  Playlist" (FASE 7, Centro de Importación); el flujo de un video se
  extrajo tal cual a `SongImport.tsx` (sin cambios de comportamiento) y se
  agregó `PlaylistImport.tsx`: tabla de canciones con selector de
  candidato por fila (cambiar coincidencia o "Ignorar", spec §9), resumen
  de cuántas se van a agregar, y bloqueo con CTA a "Conectar YouTube" si
  esa conexión no existe todavía.
- **`format.ts`**: `friendlyError` y `CONFIDENCE_LABEL` (antes solo en
  `Home.tsx`) se compartieron entre `SongImport.tsx` y `PlaylistImport.tsx`
  en vez de duplicarse una segunda vez.

### Verificado
- 49/49 tests pasan (9 nuevos: parser de playlist ID + lógica de
  `confirm_playlist_sync` con Spotify mockeado — duplicados, omitidos e
  importados se resuelven bien, y no se llama a Spotify cuando no hay nada
  para agregar).
- Rutas nuevas registradas (23 en total) y protegidas correctamente: sin
  sesión de Spotify, `/api/sync/playlist/preview` devuelve 401.
- Frontend tipa limpio y se probó en el navegador sin errores de consola.

### Qué falta de esta fase
- **"Buscar manualmente"** (spec §9) no está — solo se puede elegir entre
  los candidatos que trajo el matching automático o ignorar la canción.
  Necesitaría un endpoint de búsqueda libre en Spotify; se deja para
  cuando haga falta de verdad.
- **FASE 9 (Batch processing genérico con estados `queued/processing/...`)**
  no se implementó como abstracción aparte — el estado de cada canción ya
  vive en `SyncItemStatus`, que cubre el mismo rol para este alcance. Si en
  FASE 13 (jobs en background) hace falta más granularidad, se revisa ahí.
- Playlists de más de 50 canciones se truncan; procesarlas completas
  necesita background jobs (FASE 13), no tiene sentido antes.

## FASE 11/12/15/16 (completada 2026-09-22)

A pedido de "seguí con todo lo que sigue". Se implementó lo que agrega
valor real sin sobreingeniería (Regla 75); se pospuso explícitamente lo que
necesita infraestructura o decisiones que todavía no están justificadas.

### FASE 11 — Comparador, duplicados y fusión de playlists
- **`services/track_identity_service.py`** (nuevo, coincide con el layout
  propuesto en la spec de evolución §62): determina si dos tracks de
  Spotify son "potencialmente la misma canción" por similitud de
  título+artista (no por ISRC — el campo `external_ids.isrc` nunca se
  confirmó disponible bajo las restricciones de Development Mode de Feb
  2026, y no se quiso construir sobre un campo sin verificar, Regla 71).
- **`services/playlist_service.py`**: comparar dos playlists (coinciden /
  solo en A / solo en B), "Playlist Health" (grupos de duplicados dentro de
  una playlist), fusionar N playlists con detección de duplicados —
  deliberadamente **sin persistir en `syncs`/`sync_items`** (esas tablas
  modelan el flujo YouTube→Spotify, no operaciones Spotify-a-Spotify;
  forzar el modelo habría sido más complejo que mantenerlo stateless).
- Frontend: `/playlists` con pestañas Comparar / Salud / Fusionar.
- 12 tests nuevos de `track_identity_service` (lógica pura, sin APIs reales).

### FASE 12 — UX avanzada (parcial, a propósito)
- **Bug de contraste real encontrado y corregido**: el CSS tenía colores de
  texto fijos (`#eee`) asumiendo fondo oscuro, ignorando la preferencia de
  tema del sistema — con el navegador en modo claro, el texto habría sido
  casi invisible sobre fondo blanco. Se refactorizaron todos los colores a
  variables CSS (`--stt-*`) con tres modos: Sistema (sigue
  `prefers-color-scheme`), Claro y Oscuro explícitos, persistidos en
  `localStorage`. Verificado visualmente en el navegador en ambos modos.
- **Command palette (Ctrl+K)**: navegación + acciones rápidas, sin
  interferir con atajos del navegador (`preventDefault` solo en
  Ctrl/Cmd+K).
- **No implementado**: modo simple/avanzado y modo seguro/rápido (spec
  §20-22) necesitan una tabla `user_preferences` y una pantalla de
  configuración — no se construye antes de que haya una razón concreta
  para necesitarlos (Regla 75, "no sobreingeniería").

### FASE 15 — Testing, seguridad, observabilidad
- **`core/logging.py`**: eventos nombrados (`sync_started`,
  `sync_completed`, `token_refresh_failed`) — nunca tokens ni secretos en
  los logs (spec §65).
- **Mensaje de error humano en refresh de token fallido**: antes, si
  Spotify o Google rechazaban el refresh (por ejemplo, el token de Google
  vencido a los 7 días por no estar verificado), la excepción de `httpx` se
  propagaba sin capturar. Ahora se traduce a "Tu conexión con X expiró,
  reconectá" (spec §41) y se loguea el evento.
- **Primer test de seguridad a nivel API** (`test_api_auth.py`, con
  `TestClient` de FastAPI): confirma que los 16 endpoints que tocan datos
  de usuario o tokens externos devuelven 401 sin sesión. De paso encontró
  que `/api/spotify/disconnect` y `/api/youtube/disconnect` devuelven 200
  sin sesión — **no es una falla**, es un no-op idempotente intencional (no
  lee ni modifica nada), documentado con su propio test en vez de "arreglarlo".
- Tests de `core/crypto.py` (round-trip de cifrado, antes sin cobertura).
- Total: **76 tests** (antes 49).

### FASE 16 — Docker + CI/CD
- `backend/Dockerfile`, `frontend/Dockerfile` (build multi-stage con
  nginx, sirviendo el build de producción de Vite) + `.dockerignore` en
  ambos.
- `docker-compose.yml` ahora levanta **Postgres + backend + frontend**
  juntos (antes solo Postgres); el backend corre `alembic upgrade head`
  automáticamente antes de arrancar.
- **Verificado de verdad, no solo escrito**: se construyeron ambas
  imágenes, se levantó el stack completo con `docker compose up`, y se
  confirmó en el navegador que el frontend dockerizado sirve la app y
  habla correctamente con el backend dockerizado, que a su vez migró y
  respondió contra el Postgres dockerizado. Se usó un `.env` descartable
  con credenciales dummy solo para esta verificación (nunca commiteado,
  borrado al terminar).
- `.github/workflows/ci.yml`: tests de backend (con Postgres de servicio) +
  build de frontend. No puede ejecutarse todavía — el proyecto no tenía
  repositorio Git; se corrió `git init` (acción local, reversible) para que
  el workflow tenga dónde vivir, pero **no se hizo ningún commit** (se
  hace solo si vos lo pedís explícitamente).

### Por qué NO se implementaron FASE 13 y FASE 14

La spec de evolución es explícita: "Primero diseñar la abstracción" antes
de background jobs, y "no introducir Redis/Celery si todavía no es
necesario" (§28, §75). Hoy:
- El límite de 50 canciones por preview de playlist ya cubre el uso
  personal típico sin bloquear una request HTTP de forma problemática.
- No hay ningún usuario reportando que necesite sincronización automática
  o bidireccional — construirla ahora sería resolver un problema que no
  existe todavía (sobreingeniería, Regla 75).
- FASE 14 (bidireccional) además requiere una política explícita de
  resolución de conflictos (`source_of_truth`, `conflict_policy`) que es
  una decisión de producto, no técnica — debería definirse con el usuario
  antes de escribir una sola línea, no asumirse.

Quedan documentadas como próximo paso natural cuando/si hace falta, no
como trabajo pendiente urgente.

## Revisión de errores e inconsistencias (2026-09-22)

A pedido explícito, revisión de código (no solo de documentación) sobre
todo lo implementado hasta acá. Encontrados y corregidos:

1. **Bug real en `/api/playlists/{id}/health`**: `playlist_service.py`
   devolvía `duplicate_groups` como lista plana de tracks; el schema
   `PlaylistHealthResponse` espera `list[{"tracks": [...]}]`. Crasheaba con
   un 500 exactamente cuando había duplicados — el caso que el endpoint
   existe para mostrar. Test de regresión agregado que valida contra el
   schema Pydantic real, no solo contra el dict.
2. **Regresión de manejo de errores**: al extraer `analyze_youtube_video`
   a `sync_service.py` (FASE 7/8), se perdió el catch de
   `httpx.HTTPStatusError` que antes traducía fallas de Spotify/YouTube a
   un 502 amigable. Corregido con un manejador de excepciones global en
   `main.py` (cubre todos los endpoints, no solo los dos que lo tenían
   antes) + el callback de OAuth de Spotify ahora también redirige con
   mensaje de error en vez de tirar un 500 crudo (ya lo hacía el de
   YouTube).
3. **Mensaje de error con el proveedor equivocado**: `friendlyError` en el
   frontend pisaba el mensaje del backend con un "Tu conexión con Spotify
   expiró" fijo para cualquier 401 — en el flujo de playlist (que necesita
   Spotify Y YouTube) le decía al usuario que reconecte el proveedor
   equivocado. Corregido para usar el mensaje que ya arma el backend
   (correcto por proveedor), y el link de "Reconectar" ahora apunta al
   proveedor correcto.
4. **Historial mostraba solo la primera canción de una playlist**: `Sync`
   soporta N items desde FASE 2, pero `History.tsx` solo mostraba
   `items[0]`, ocultando el resto (hasta 49 canciones) para syncs de
   playlist. Ahora resume conteos (agregadas/duplicadas/ignoradas) cuando
   hay más de un item.
5. **Código muerto**: `LookupResult` en `schemas/youtube.py`, sobrante del
   endpoint `api/youtube.py` que se eliminó en FASE 7/8.
6. **Comentarios desactualizados** en `core/config.py` (decían "no usado
   todavía" sobre las credenciales de Google, que ya están en uso desde
   FASE 5; puerto de ejemplo con el 5432 viejo en vez del 5434 real).

No se encontraron problemas de seguridad nuevos (ownership, cifrado de
tokens y CORS ya se habían revisado en FASE 15). 78/78 tests pasan
después de los fixes (incluye 2 tests nuevos de regresión).

## FASE 12 (resto) — Modo simple/avanzado y modo seguro/rápido (completada 2026-09-22)

Confirmado con el usuario: **FASE 13 (jobs) y FASE 14 (sync automática/
bidireccional) quedan salteadas** — no hay un problema real que justifique
la infraestructura todavía, y bidireccional necesitaría una política de
conflictos que nadie pidió definir. Documentado como decisión, no como
pendiente.

### Qué se hizo
- **`frontend/src/settings.ts`**: preferencias en `localStorage` (como el
  tema) — no se creó una tabla `user_preferences` en el backend porque es
  una preferencia de UI por navegador, no algo que necesite sincronizarse
  entre dispositivos ni ser aplicado del lado del servidor.
- **Modo simple/avanzado**: toggle de visualización. Simple oculta el % de
  confianza y la posibilidad de elegir otro candidato (`SongImport.tsx`,
  `PlaylistImport.tsx`); avanzado es el comportamiento de siempre.
- **Modo seguro/rápido**: en rápido, una canción individual con confianza
  ≥ umbral configurable (default 95%) se confirma sola apenas se elige la
  playlist destino, sin el clic extra de "Confirmar cambios". **Nunca
  aplica a playlists** — se mantienen siempre con confirmación explícita,
  seas cual sea el modo, porque el propio spec (§21) dice que las
  operaciones grandes no deben perder ese paso de seguridad.
- Nueva página `/settings`, accesible desde el nav y desde el command
  palette (Ctrl+K).

### Verificado
- 78/78 tests de backend siguen pasando (este cambio es 100% frontend).
- Frontend tipa limpio.
- Probado en el navegador sin errores de consola (la pantalla `/settings`
  en sí no se pudo probar interactivamente todavía — requiere estar
  autenticado, y seguimos sin credenciales reales cargadas).


## Mejoras de robustez y límites (2026-09-23)

A pedido: arreglar con código todo lo que se pueda de las limitaciones
conocidas. Lo que depende de Spotify/Google (Premium, tope de 5 usuarios,
tokens de Google que vencen a los 7 días) no se puede resolver acá.

- **Playlists de Spotify paginadas**: `get_user_playlists` seguía solo las
  primeras 50; ahora sigue los links `next` (con tope de 100 páginas).
- **Respuestas externas validadas**: un 2xx de Spotify/YouTube con una
  forma inesperada ahora levanta `ExternalResponseError` → 502 con mensaje
  claro y log del detalle, en vez de un `KeyError` → 500 crudo. El parseo
  de tracks se unificó en `_parse_track` (antes estaba duplicado en dos
  lugares). Las entradas de playlist aceptan tanto la clave `track` como
  `item` (la migración de Spotify de feb 2026 renombró campos de playlist
  y no pudimos confirmar cuál queda), y se saltean archivos locales,
  tracks removidos y episodios de podcast.
- **Playlists de más de 50 canciones**: se procesan por tandas
  (`offset`/`next_offset`); cada tanda es un Sync propio, revisable y
  confirmable. Sin jobs en background.
- **Buscar manualmente** (`GET /api/spotify/search`) en el flujo de una
  canción y en cada fila de una playlist. Un track elegido a mano se
  guarda **sin** confianza (no hay score real) y nunca dispara el
  auto-confirm del modo rápido.
- **Bug corregido de paso**: la etiqueta "siguientes canciones (X–Y de N)"
  calculaba mal el rango; lo encontró un test nuevo.
- **Tests**: backend 78 → 90 (paginación, forma de respuestas, tandas,
  handler 502, búsqueda protegida); frontend 22 → 32 (flujos completos de
  `SongImport` y `PlaylistImport`, incluido el auto-confirm del modo
  rápido y su exclusión para picks manuales, y `ManualSearch`).

Sigue sin verificarse contra la API real de Spotify: las hipótesis sobre
forma de respuesta ahora fallan de manera controlada, pero la primera
prueba con credenciales reales sigue siendo lo que las confirma.
