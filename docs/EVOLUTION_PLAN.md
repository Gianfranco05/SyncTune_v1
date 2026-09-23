# SyncTune — Plan de evolución

Análisis previo a implementar la especificación de evolución (77 secciones,
de "IMPORTAR/ORGANIZAR/SINCRONIZAR/ANALIZAR"), siguiendo el protocolo del
agente: **INSPECT → esto es ese entregable → PLAN (al final) → recién
después IMPLEMENT**. No se escribió código de features nuevas en este
documento — solo investigación y planificación, como pide la sección 78.

## 1. Estado real del código (inspección)

### Backend — inventario exacto

```
backend/app/
├── main.py                    # monta spotify.router + sync.router, CORS, SessionMiddleware
├── api/
│   ├── spotify.py              # 8 endpoints (login, callback, me, logout,
│   │                            #  disconnect, playlists GET/POST, tracks POST)
│   └── sync.py                 # 4 endpoints (preview, confirm, history, detail)
├── services/
│   ├── spotify_service.py      # OAuth, search, playlists, get_playlist_track_ids
│   ├── youtube_service.py      # extract_video_id, fetch_video_title (API key, sin OAuth)
│   ├── matching_service.py     # clean_title, guess_artist_track, build_search_queries,
│   │                            #  detect_version, confidence_level, score_candidate
│   └── sync_service.py         # analyze_youtube_video, create_pending_sync, confirm_sync
├── models/
│   ├── user.py                 # id, email (nullable), created_at, updated_at
│   ├── connection.py            # provider (enum: spotify|youtube ya definido),
│   │                            #  provider_account_id, tokens cifrados, expires_at
│   ├── sync.py                  # source, destination, status (9 estados del spec original)
│   └── sync_item.py             # source_*/destination_*, status, confidence
├── schemas/                    # Pydantic: spotify.py, sync.py, youtube.py
├── core/
│   ├── config.py                # Settings (pydantic-settings)
│   ├── database.py              # SQLAlchemy SYNC (psycopg2), no async
│   ├── security.py              # get_current_connection / get_valid_access_token /
│   │                            #  get_current_user_id (Depends chain)
│   └── crypto.py                # Fernet derivado de SECRET_KEY
└── tests/                      # 21 funciones de test (35 casos con parametrize):
    ├── test_matching_service.py  # 18 funciones — incluye los 4 ejemplos del spec §62
    └── test_youtube_service.py   # 3 funciones — parser de URL + duración ISO8601
```

**Importante para esta fase**: `models/connection.py` **ya tiene**
`Provider.youtube` en el enum (se agregó en FASE 2 previendo esto), pero
**ningún código lo usa todavía** — no hay `youtube_service.build_auth_url`,
ni callback, ni refresh. Es decir: el modelo de datos para FASE 5 ya existe,
falta el flujo OAuth en sí.

### Frontend — inventario exacto

```
frontend/src/
├── main.tsx          # BrowserRouter
├── App.tsx            # shell: header + nav (Sincronizar/Historial) + Routes
├── api.ts              # cliente fetch tipado, ApiError con .status
├── types.ts             # tipos calcados 1:1 de los schemas Pydantic
└── pages/
    ├── Home.tsx          # onboarding si no autenticado; si autenticado: search → preview
    │                     #  → candidatos con badge de confianza → playlist picker → confirm
    └── History.tsx        # lista de syncs con status pill
```

No existe: command palette, dashboard, pantalla de conexiones, centro de
importación, comparador, limpiador, inbox, configuración, temas, ningún
componente reutilizable separado (todo vive inline en las 2 páginas).

### Lo que el flujo actual **no** hace (aunque el modelo lo prevé)
- Un `Sync` siempre tiene `source="youtube"`, `destination="spotify"` fijos
  y exactamente 1 `SyncItem` — el modelo ya soporta N items por sync
  (`sync.items: list[SyncItem]`), pero nada crea más de uno todavía. Esto es
  clave: **FASE 8 (playlist) no necesita cambiar el esquema de `syncs`/
  `sync_items`**, solo el código que los llena.
- No existe `track_mappings` (aprendizaje de decisiones, sección 11).
- No existe ninguna tabla de jobs/batch (secciones 9, 28).
- El único servicio de matching es `matching_service.py`; no hay
  `track_identity_service.py`, `playlist_service.py`, `job_service.py`,
  `history_service.py`, `analytics_service.py`, `conflict_service.py`
  (sección 62 de la nueva spec).

## 2. Diferencias entre la spec de evolución y el código actual

| Área de la nueva spec | Estado |
|---|---|
| YouTube OAuth (§5) | ⬜ No existe. `Provider.youtube` ya está en el enum del modelo. |
| Centro de conexiones (§6) | ⬜ No existe (no hay pantalla de Settings). |
| Centro de importación (§7) | ⬜ No existe (Home.tsx solo soporta 1 video a la vez). |
| Importar playlist YT→Spotify (§8) | ⬜ No existe. `sync_service.py` está escrito para 1 sola canción. |
| Matching con más señales (§10) | 🟡 Ya soportamos 7 tags de versión (live/acoustic/remix/remastered/instrumental/karaoke/cover). Faltan: radio edit, extended, sped up, slowed, y separar "official video/audio/music video/visualizer" como señales explícitas (hoy solo se usan para limpiar el título, no se puntúan). |
| `track_mappings` / aprendizaje (§11) | ⬜ No existe tabla ni lógica. |
| Batch processing genérico (§12) | ⬜ No existe. |
| Dashboard + estadísticas (§13-14) | ⬜ No existe. Los datos para calcularlas SÍ existen en `syncs`/`sync_items`. |
| Comparador de playlists (§15-16) | ⬜ No existe. No hay `track_identity_service.py`. |
| Fusionar playlists (§17) | ⬜ No existe. |
| Limpiador / Playlist Health (§18-19) | ⬜ No existe. |
| Modo simple/avanzado, seguro/rápido (§20-22) | ⬜ No existe (un solo modo hoy). |
| Command palette / búsqueda global (§23-24) | ⬜ No existe. |
| Historial 2.0, repetir, undo (§25-27) | 🟡 Historial básico existe (`/history`). Repetir/undo no. |
| Jobs en background + progreso (§28-30) | ⬜ No existe — todo es síncrono request/response hoy. |
| Reintentos + rate limiting + cache (§31-33) | ⬜ No existe ninguna capa central; `httpx` se llama directo en cada `*_service.py`. |
| Sync incremental (§34-35) | ⬜ No existe — cada preview reprocesa todo. |
| Sync automática / bidireccional (§36-38) | ⬜ No existe. |
| Music Inbox (§39) | ⬜ No existe. |
| Preferencias de matching, favoritos (§44-45) | ⬜ No existe (umbrales son constantes de código, no configurables por UI). |
| Configuración de sync (§46) | ⬜ No existe. |
| Onboarding, empty states, errores humanos (§47-49) | 🟡 Onboarding básico y errores 401 mapeados ya existen; falta cubrir 403/404/timeouts con el mismo criterio. |
| Ownership checks (§58) | ✅ Ya implementado: todo endpoint de `sync.py` filtra por `Sync.user_id == user_id`; nunca confía en IDs del frontend para autorizar. |
| Auditoría / logs estructurados (§59, §65) | ⬜ No existe logging estructurado; solo los logs default de uvicorn. |
| Paginación (§64) | ⬜ `GET /api/sync/history` devuelve todo sin paginar (hoy es inofensivo con 1 sync por video, pero se rompe con playlists de FASE 8). |
| Feature flags (§70) | ⬜ No existe. |
| ADRs / docs/ (§68-69) | ⬜ Solo existen `README.md` e `IMPLEMENTATION_PLAN.md` en la raíz. |

## 3. Investigación de APIs externas (paso 4 del protocolo)

### YouTube OAuth / Google Identity — hallazgos nuevos

Fuentes: [OAuth 2.0 scopes de Google](https://developers.google.com/identity/protocols/oauth2/scopes),
[Server-side web apps (YouTube)](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps),
[App audience / testing status](https://support.google.com/cloud/answer/15549945),
[Unverified apps](https://support.google.com/cloud/answer/7454865).

1. **Scope necesario**: `https://www.googleapis.com/auth/youtube.readonly`
   alcanza para todo lo que pide la sección 5 de la nueva spec (leer
   playlists propias, incluidas privadas, y sus items) — no hace falta el
   scope completo `youtube` (que permite modificar) ni `youtube.force-ssl`.
   Menor scope = menor fricción de verificación (Regla del spec: pedir el
   mínimo necesario).
2. **Riesgo real, análogo al de Spotify**: mientras el proyecto de Google
   Cloud esté en estado **"Testing"** (que es donde va a estar un proyecto
   personal, igual que Spotify Development Mode):
   - Tope de **100 test users** listados a mano en la pantalla de consentimiento
     — mucho más holgado que el tope de 5 de Spotify.
   - **Los refresh tokens expiran a los 7 días** para apps no verificadas.
     Esto es un hallazgo **crítico** que la spec original no menciona: sin
     pasar por verificación de Google, cualquier sincronización automática
     o incremental (FASE 14) dejaría de funcionar cada 7 días hasta que el
     usuario vuelva a autorizar manualmente. Verificar una app con un scope
     "sensible" (que `youtube.readonly` probablemente es, a confirmar al
     implementar) toma semanas y pide una razón de negocio — no tiene
     sentido para un proyecto personal.
   - **Decisión propuesta** (a confirmar contigo antes de FASE 5): aceptar
     la reautenticación cada 7 días como limitación conocida — igual que ya
     aceptamos el tope de 5 usuarios de Spotify — y mostrarlo en el Centro
     de Conexiones (§6) como "expira pronto, reconectá" en vez de fallar
     silenciosamente.
3. **Costo de cuota para importar playlists** (relevante para FASE 8): una
   playlist de YouTube se lee con `playlistItems.list` (1 unidad, hasta 50
   items por página) + `videos.list` (1 unidad, hasta 50 ids por request) —
   una playlist de 200 canciones cuesta ~8 unidades, insignificante contra
   el cupo de 10.000/día. Confirma que la decisión de FASE 0 de evitar
   `search.list` en YouTube sigue siendo la correcta para FASE 8.

### Spotify — nada nuevo que cambie lo ya documentado en FASE 0

No hay cambios adicionales de API detectados desde la última verificación.
Lo que sí es nuevo para esta etapa: **detección de duplicados a escala** —
`get_playlist_track_ids` ya pagina con `next`, así que soporta playlists de
Spotify grandes sin cambios (relevante para FASE 8/11).

## 4. Dependencias entre fases (grafo, no solo lista)

```
FASE 5 (YouTube OAuth)
   │
   ├──> FASE 6 (Centro de conexiones) — muestra el estado de ambas conexiones
   │
   └──> FASE 8 (Importar playlist) ──> FASE 9 (Batch processing genérico)
              │                              │
              │                              └──> FASE 13 (Jobs en background)
              │                                         │
              └──> FASE 34/35 (Sync incremental) ───────┴──> FASE 36 (Sync automática)
                                                                    │
                                                         FASE 37 (Bidireccional)

FASE 10 (Dashboard) — depende solo de datos que YA existen (syncs/sync_items).
  No depende de FASE 5. Se podría adelantar.

FASE 15/16 (Comparador/Fusionar/Limpiar) — depende de tener M > 1 playlists
  sincronizadas para que tenga sentido comparar. Sin FASE 8, es una feature
  sin datos reales para probar.

track_mappings (§11) — no depende de nada nuevo, se puede agregar en
  paralelo a FASE 8 (se llena la primera vez que el usuario confirma una
  coincidencia manual).
```

**Conclusión de dependencias**: el orden de la sección 72 de la spec
(5→6→7→8→9→10→11→12→13→14→15→16) es razonable, con una excepción: **FASE
10 (Dashboard básico) no depende de FASE 5-9** y se puede hacer antes o en
paralelo sin ningún riesgo, porque toda la data ya existe en `syncs`/
`sync_items`. Lo dejo como sugerencia de reordenamiento, no como decisión
tomada.

## 5. Riesgos identificados

| Riesgo | Impacto | Mitigación propuesta |
|---|---|---|
| Refresh token de Google expira a los 7 días en modo Testing | Alto para FASE 14 (auto-sync), bajo para FASE 5-8 (uso manual) | Documentarlo igual que el límite de Spotify; UI que avise "reconectá YouTube" en vez de fallar en silencio |
| `sync_service.py` está escrito 1:1 para "un video → un track" | Medio | Antes de FASE 8 hay que decidir si se generaliza `sync_service.py` (una función que reciba N items) o se crea un `playlist_sync_service.py` separado que reutilice `matching_service`/`spotify_service` — **esto es una decisión de diseño a tomar en el PLAN de FASE 8, no ahora** |
| Sin paginación en `/api/sync/history` | Bajo hoy, alto después de FASE 8 | Paginar antes de que existan syncs con muchos items (FASE 8, no antes) |
| Sin capa de rate limiting/retry central | Medio — cada `*_service.py` llama `httpx` directo sin reintentos | Se vuelve necesario recién cuando aparezcan operaciones batch grandes (FASE 8-9), no antes — evita sobreingeniería prematura |
| Tope de 5 usuarios de Spotify + reautenticación de 7 días de Google combinados | Bajo para un proyecto personal, pero **hay que decidir explícitamente** si vale la pena construir auto-sync (FASE 36) sabiendo que se rompe cada 7 días sin verificación de Google | Confirmar con vos antes de FASE 14, no bloquea FASES 5-13 |

## 6. Funcionalidades ya técnicamente posibles (sin trabajo adicional de investigación)

- FASE 5 (YouTube OAuth) — investigación ya hecha en este documento, lista para implementar.
- FASE 6 (Centro de conexiones) — solo necesita datos que `connections` ya expone.
- FASE 10 (Dashboard básico) — los números salen de `COUNT`/`GROUP BY` sobre `syncs`/`sync_items`, sin research adicional.
- Historial 2.0 parcial (más detalle por sync) — el modelo ya tiene los campos.

## 7. Funcionalidades que requieren validación antes de implementar

- **FASE 8 (import de playlist)**: decidir el diseño de `sync_service.py` vs. un servicio nuevo (ver riesgos).
- **`track_identity_service.py` con ISRC (§16)**: hay que verificar si el objeto track de Spotify Search sigue exponiendo `external_ids.isrc` bajo las restricciones de Development Mode de Feb 2026 (no confirmado todavía — la lista de campos removidos que documentamos en FASE 0 no lo menciona, pero no se verificó explícitamente).
- **Undo (§27)**: Spotify no tiene endpoint de "deshacer" — un undo real es "eliminar esos track_uris específicos de la playlist" vía `DELETE /playlists/{id}/items`, que si repasás la migración de Feb 2026 sí sigue existiendo. Falta confirmar el formato exacto del body de ese DELETE en la doc actual antes de prometer undo.
- **Verificación de app de Google**: si en algún momento se quisiera pasar de 100 test users, confirmar el proceso real (seis semanas, según lo investigado) — no es necesario para las fases 5-13.

## 8. Orden de implementación propuesto

Confirmo el orden de la sección 72 de la spec, con la única sugerencia de
adelantar el Dashboard (ver sección 4 de este documento):

1. **FASE 5 — YouTube OAuth** (siguiente paso, scope `youtube.readonly` únicamente)
2. **FASE 6 — Centro de conexiones**
3. *(sugerido, opcional)* **FASE 10 — Dashboard básico**, en paralelo, porque no tiene dependencias
4. **FASE 7 — Centro de importación** (UI, todavía sin playlist real)
5. **FASE 8 — Importar playlist YouTube → Spotify**
6. **FASE 9 — Batch processing genérico**
7. **FASE 11 — Comparador + duplicados + fusionar + limpiar**
8. **FASE 12 — UX avanzada**
9. **FASE 13 — Jobs en background + progreso**
10. **FASE 14 — Incremental + automática + bidireccional**
11. **FASE 15 — Testing profundo + seguridad + observabilidad**
12. **FASE 16 — Docker + CI/CD + deployment**

## 9. Decisiones confirmadas (2026-09-22)

1. **Orden de fases**: se adelanta el Dashboard básico (FASE 10) para
   hacerlo después de FASE 6, en paralelo con FASE 7 — no depende de
   YouTube OAuth y da una victoria visible temprano.
2. **OAuth de Google**: se acepta la reautenticación cada 7 días mientras
   la app esté en modo "Testing" (sin verificar), igual que ya se aceptó el
   tope de 5 usuarios de Spotify Development Mode. Se documenta en el
   Centro de Conexiones (FASE 6) y no bloquea el desarrollo de FASE 5-13.

Orden final: **FASE 5 → FASE 6 → FASE 10 (adelantada) → FASE 7 → FASE 8 →
FASE 9 → FASE 11 → FASE 12 → FASE 13 → FASE 14 → FASE 15 → FASE 16**.

## 10. Progreso (actualizado 2026-09-22)

- ✅ **FASE 5 — YouTube OAuth**: completa. Detalle en
  `IMPLEMENTATION_PLAN.md` ("FASE 5/6 — YouTube OAuth + Centro de
  Conexiones").
- ✅ **FASE 6 — Centro de Conexiones**: completa, misma entrega que FASE 5.
- ✅ **FASE 10 — Dashboard básico**: completa (adelantada). Detalle en
  `IMPLEMENTATION_PLAN.md` ("FASE 10 — Dashboard básico"). Primer test de
  integración del proyecto contra Postgres real.
- ✅ **FASE 7 — Centro de Importación** y **FASE 8 — Importar playlist
  YouTube → Spotify**: completas, implementadas juntas a pedido explícito
  (la canción sigue siendo el flujo principal, la playlist tenía que andar
  también). Detalle en `IMPLEMENTATION_PLAN.md` ("FASE 7/8"). Primer uso
  real del token de YouTube conectado en FASE 5.
- **FASE 9 — Batch processing genérico**: evaluada y no implementada como
  abstracción aparte — `SyncItemStatus` ya cubre el mismo rol para el
  alcance actual; se revisa si hace falta más al llegar a FASE 13.
- ✅ **FASE 11 — Comparador + duplicados + fusionar**: completa
  (`track_identity_service.py`, `playlist_service.py`, `/playlists`).
- 🟡 **FASE 12 — UX avanzada**: command palette (Ctrl+K) + tema
  claro/oscuro/sistema (de paso, corrigió un bug real de contraste con
  tema claro). Modo simple/avanzado y modo seguro/rápido quedan pendientes
  — necesitan `user_preferences` + pantalla de configuración, sin
  justificación todavía (Regla 75).
- ✅ **FASE 15 — Testing/seguridad/observabilidad**: logging estructurado
  sin secretos, mensajes de error humanos en fallos de refresh de token,
  76 tests totales (incluye el primer test de seguridad a nivel API).
- ✅ **FASE 16 — Docker + CI**: `docker-compose.yml` levanta el stack
  completo (Postgres + backend + frontend), verificado end-to-end con un
  `docker compose up` real. `.github/workflows/ci.yml` listo para cuando
  el proyecto tenga un remoto de GitHub — se inicializó git localmente
  (`git init`, sin commits) para que tenga dónde vivir.
- ⬜ **Pospuestas deliberadamente — FASE 13 (jobs en background) y FASE 14
  (incremental/automática/bidireccional)**: sin un problema real que
  resolver todavía (el cap de 50 canciones por playlist alcanza para uso
  personal) y, para FASE 14 en particular, sin una política de resolución
  de conflictos definida con el usuario — construirlas ahora sería
  sobreingeniería (Regla 75) y una decisión de producto tomada sin
  consultar. Detalle completo de la justificación en
  `IMPLEMENTATION_PLAN.md` ("Por qué NO se implementaron FASE 13 y FASE 14").
