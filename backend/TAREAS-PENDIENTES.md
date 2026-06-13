# TAREAS PENDIENTES — SFA Backend

---

## SESIÓN 2026-05-26 — Qué se hizo y qué queda pendiente (LEER PRIMERO)

### Cambios aplicados

**Frontend: perfil de jugador completamente rediseñado ✓**

- **`HighlightsView.tsx`** — reescritura completa: 15 tipos de tarjetas (antes 12), chips por tarjeta, tarjetas clickables abren modal con lista de partidos. 3 nuevas tarjetas: GOLES EN PRESIÓN (m3≥1.6, min 2), ACTUACIONES ÉLITE (sfa_pts≥2500, min 2), MOMENTOS CLAVE (m3≥1.3, min 3). Se eliminó el bloque "Tipos de Gol" (sustituido por PointsBreakdown). Bug corregido: `useMemo` devolvía objeto `{cards, goalBreakdown}` → ahora devuelve `Card[]` directamente.

- **`StatBar.tsx`** — rediseño como tarjetas flotantes individuales con dos grupos: primario (partidos, minutos, goles, asistencias, regates, etc.) y técnico (pases completados con %, disparos tot., duelos tot., etc. — solo si `seasonStats` disponible). Se eliminó SFA Total (ya visible en header). Pases completados muestra solo cantidad + porcentaje de precisión abajo. "Reg. sufridos" solo para DC/GK. "Penales gen." (no "Penales gan."). Fusionado con `AdvancedStatsBar` (que ya no se usa).

- **`PointsBreakdown.tsx`** — nuevo componente: lista desplegable acordeón con 3 secciones ("Creación y ataque", "Duelos y defensa", "Disciplina"). Eventos individuales con pts exactos del backend; stats agregadas (regates, duelos, tackles, intercepciones, bloqueos, faltas rec.) con pts estimados (marcados `~`). Colocado en PlayerPage después del historial de partidos.

- **`PlayerPage.tsx`** — wiring de `seasonStats`: busca `competition_id` por nombre en la lista de competiciones, luego llama `fetchPlayerSeasonStats`. Eliminados `AdvancedStatsBar` y `SeasonActions` (redundante). `PointsBreakdown` añadido.

- **`client.ts`** — `fetchPlayerSeasonStats(id, competitionId, season)` con cache TTL.

- **`types/index.ts`** — interfaz `PlayerSeasonStats` añadida.

**Clarificación arquitectónica: xa_no_assist ✓**
- `xa_no_assist` NO es un evento separado en `player_events`. Se calcula dentro del evento STATS como `max(0, passes_key - assists)`. Yamal: 94 pases clave - 21 asistencias = 73 xa_no_assist → ya incluido en sus 40,639 pts de STATS. El scoring es correcto.
- `player.breakdown` solo contiene tipos de eventos que existen en `player_events` (goal, assist, corner_assist, goal_penalty, etc.). Las acciones de `player_stats` (regates, duelos, tackles) NO tienen breakdown individual — PointsBreakdown las estima con `BASE_PTS`.

### Pendiente inmediato

- [ ] **Comparador (`/compare`)** — ruta ya existe como placeholder. Módulo a construir mañana.
- [ ] **Equipos (`/teams`)** — ruta ya existe como placeholder. Módulo a construir para beta del Mundial.
- [ ] **`AdvancedStatsBar.tsx`** — archivo huérfano (ya no se importa en ningún lado). Eliminar.

---

## SESIÓN 2026-05-24/25 — Qué se hizo y qué queda pendiente

### Cambios aplicados

**Spec 0010: API-Football Complete Stats — completamente implementado ✓**
- Modelo: 8 columnas FBref-only eliminadas; 11 nuevas + `rating` Numeric(4,2).
- Ingesta: `PlayerStatsRawDTO` con 11 campos nuevos en `api_football.py` + `upsert_player_stats`.
- Scoring: 6 nuevos `ActionType` (PASSES_COMPLETED MF=8, señales negativas tarjetas/faltas).
- `GET /players/{id}/stats` implementado con `GetPlayerSeasonStatsUseCase`.
- `POST /admin/backfill-fixture-stats` + `BackfillFixtureStatsUseCase` + Celery task.
- `enrich_all_task` ya solo recalcula (sin scrapers FBref/Understat).
- Migración aplicada vía `scripts/migrate_0010_player_stats.py`.
- Backfill corrido para las ligas principales (campos nuevos poblados en BD).
- Recalculate corrido para todas las competiciones con scoring actualizado.

**Sistema MVP/rating — MratingFactor ✓**
- `MratingFactor` en `value_objects.py`: None→0.75, <7→0.5, [7,8)→0.85, [8,8.5)→1.0, ≥8.5→1.25.
- `score_match_stats()` aplica MratingFactor para STATS events.

**Frontend: nuevas features ✓**
- `RankingCard.tsx` — nueva tarjeta de ranking.
- `SeasonActions.tsx` — chips de acciones de temporada con pts breakdown.
- `HighlightsView.tsx` — 12 tipos de highlights (hat tricks, goles valiosos, rachas, vs élite…).
- `RankingPage` — paginación PAGE_SIZE=8 + búsqueda server-side con debounce 350ms.
- `client.ts` — cache in-memory TTL 60s + parámetro `name` en fetchRanking.
- Skeleton loading states en `PlayerPage`.
- Stages de copas nacionales sembrados en BD.

### Pendiente inmediato

- [x] **`ActionValues.tsx`** — actualizado con valores reales del backend. Nuevas acciones (penal ganado, interceptación, pases completados) y negativas (tarjetas, faltas). CSS `.av-item--neg` y `.av-item__note` añadidos.
- [x] **`HighlightsView`** — integrado en `FixtureList` como tab "Destacados" (vista por defecto). Reescrito completamente en sesión 2026-05-26 (ver arriba).
- [x] **`SeasonActions` en `PlayerPage`** — descartado como redundante. Las acciones de temporada ya se muestran en StatBar + PointsBreakdown.

---

## SESIÓN 2026-05-22 (noche) — Qué se hizo y qué queda pendiente

### Cambios aplicados en esta sesión

**Posiciones de jugadores corregidas ✓**
- `KNOWN_POSITIONS` expandido de ~60 a ~200 entradas en `domain/position_mapping.py`.
- Bug "Victor Boniface" → "Victor Okoh Boniface" corregido.
- 96 jugadores actualizados directamente en BD: 45 → DEL, 40 → EXT, 11 → LAT.
- Bellingham y Cole Palmer corregidos a MC (eran EXT por error).
- Recalculate corrido para las 12 competiciones.

**Ingesta de copas nacionales completada ✓**
- Copa del Rey (22), Supercopa (23), FA Cup (90), DFB-Pokal (92), Coppa Italia (94), Coupe de France (96) ingestadas.
- `top_n` cambiado de 8 → **16** para todas las copas en `ingest_competition.py`.
- Celery Beat fix: `crontab(hour="*/8")` → `crontab(hour="*/8", minute=0)` — antes disparaba 60 veces/hora.

**BASE_POINTS_TABLE recalibrada ✓**
- MF: gol 850→700, asistencia 650→520, xa_no_assist 120→**200**, dribbles 180→100, duels 40→20.
- DF: gol 1300→1000, asistencia 950→720, dribbles 280→130, duels 50→25, tackles 100→80.
- Worker reiniciado (`docker compose restart celery_worker`) para recargar módulo Python.
- Recalculate corrido para las 12 competiciones con nuevos valores.
- Ranking resultante: Yamal #1, Dembélé #2, Raphinha #3, Bellingham #4, Hakimi #5, Mbappé #7.

**Frontend: partidos excelentes en dorado ✓**
- `FixtureRow.tsx`: clase `.fixture-row--excellent` cuando `sfa_pts ≥ 3000`.
- CSS: borde izquierdo dorado 3px + gradiente gold sutil.

---

### Pendiente inmediato

- [ ] **`ActionValues.tsx` desincronizado** — el frontend muestra base_pts viejos. Actualizar con tabla recalibrada.
- [ ] **`seed_competition_stages.py`** — ejecutar para FA Cup/DFB-Pokal/Coppa Italia/Coupe de France.
- [ ] **Sistema MVP rating** — `games.rating ≥ 9.0` de API-Football como multiplicador. Invocar `@Architecture-Engineer` para spec.
- [ ] **Verificar `passes_key` en BD** — `SELECT AVG(passes_key), COUNT(*) FROM player_stats WHERE season=2024 AND passes_key > 0`. Si está vacío, xa_no_assist=200 no tiene efecto práctico.

---

## SESIÓN 2026-05-22 — Qué se hizo y qué queda pendiente (LEER PRIMERO)

### Cambios aplicados en esta sesión

**RecalculateScoresUseCase sincronizado ✓**
- `enrichment_ports.py` → `PlayerStatsEventRecalcRow` ahora incluye `passes_key, shots_on, fouls_drawn, clearances, goals, assists`.
- `enrichment_repository.py` → `get_stats_events_for_recalc` fetches esas columnas de `player_stats`.
- `recalculate_scores.py` Phase 2 ahora usa los 8 stats completos (igual que `ingest_competition.py`):
  - `XA_NO_ASSIST = max(0, passes_key - assists)` · `XG_NO_GOAL = max(0, shots_on - goals)`
  - `FOULS_DRAWN` · `CLEARANCES` — antes completamente ignorados.
  - Multiplier = `max(0.3, min(4.0, m1))` — M1 solo, sin M2. Antes usaba `m1 * m2`.
- `_STATS_ACTIONS` list eliminada (era código muerto).

**ingest_competition.py: m2=1.0 para STATS events ✓**
- Antes almacenaba `m2=stage_factor` en la columna aunque los pts se calculaban con `stage_factor=1.0`.
- Ahora guarda `m2=1.0` consistentemente para STATS events.
- El DB ya tiene m2=1.0 para todos los STATS events existentes (lo corrigió `recalculate_all_scores.py`).

**4 copas nacionales añadidas a LEAGUES ✓**
- FA Cup (id=45, standings=Premier League id=39)
- Coupe de France (id=66, standings=Ligue 1 id=61)
- DFB-Pokal (id=81, standings=Bundesliga id=78)
- Coppa Italia (id=137, standings=Serie A id=135)
- Todas con `comp_factor=1.0, top_n=8`.

**scripts/seed_competition_stages.py creado ✓**
- Reemplaza la inserción manual de competition_stages.
- Cubre todas las competiciones incluyendo las 4 nuevas copas.
- Usar ON CONFLICT DO UPDATE → seguro para re-ejecutar.
- EJECUTAR DESPUÉS de ingestar las nuevas copas.

---

### Pendiente: ingestar las 4 nuevas copas

```
POST /admin/ingest/45     # FA Cup
POST /admin/ingest/66     # Coupe de France
POST /admin/ingest/81     # DFB-Pokal
POST /admin/ingest/137    # Coppa Italia
```

Luego ejecutar:
```
python scripts/seed_competition_stages.py
```

---

## SESIÓN 2026-05-21 — Qué se hizo

**Bug crítico corregido: GOAL events faltantes**
- `_name_matches()` en `ingest_competition.py` fallaba con nombres abreviados (`"E. Haaland"` ≠ `"Erling Haaland"`).
- 825 jugadores con 2,720 goles reales sin GOAL events → cero puntos SFA por goles.
- Fix en código: `_name_matches` ahora detecta patrón `"X. Apellido"` y matchea por apellido.
- Fix en datos: `repair_missing_goal_events.py` (root del proyecto) insertó 2,741 GOAL + 1,844 ASSIST events sintéticos.

**Calibración del scoring**
- `competition_stages` estaba vacía → M2=1.0 siempre → CL valía igual que Liga.
- `competition_stages` poblada: CL group=1.5, r16=1.8, quarter=2.0, semi=2.3, final=2.8; Ligas=1.0; Copa=0.9→1.4.
- `DUELS_WON` reducido en `services.py`: FW 80→30, MF 100→40, DF 120→50.
- STATS events ahora usan solo M1 (no M2): `ingest_competition.py` pasa `stage_factor=1.0` a `score_match_stats`.
- Razón: M2 debe premiar acciones decisivas (goles, asistencias), no stats de fondo.
- `recalculate_all_scores.py` (root) recalculó 41,412 eventos y 4,053 season scores.

**Fotos de jugadores**
- 3,139 players tenían `photo_url = NULL` → poblados con URL de API-Football.
- `backfill_wikipedia_photos.py` (root) reemplaza con imágenes de Wikipedia (mayor calidad).
- Verificar estado: `SELECT COUNT(*) FROM players WHERE photo_url LIKE '%wikimedia%'`.

**Ranking resultante post-fix**
1. Mbappé: 82,376 pts | 2. Lamine Yamal: 74,912 | 3. Raphinha: 70,396
4. Kane: 68,703 | 5. Guirassy: 67,564 | 6. Bellingham: 67,248
7. Salah: 66,195 | 8. Dembélé: 63,261 | 9. Vinícius: 62,479 | 10. Hakimi: 62,269
Haaland: ~53,657 pts (~#20)

---

### Scripts standalone en root del proyecto (deuda técnica — no tocar)
- `repair_missing_goal_events.py` — inserta en `player_events` directo con psycopg2
- `recalculate_all_scores.py` — recalcula `sfa_season_scores` directo con psycopg2
- `backfill_wikipedia_photos.py` — actualiza `players.photo_url` directo con psycopg2
- `check_ranking.py` — helper temporal de verificación

Estos scripts NO pasan por Router → Use Case → Repository. Violación de la regla hexagonal. No usarlos para nuevas operaciones — usar los endpoints admin en su lugar.

---

### Plan concreto para mañana

1. **`/sfa-spec` para formalizar calibración de scoring**
   - Crear `specs/refactor/NNNN-scoring-calibration/decisions.md + plan.md`
   - Documentar: DUELS_WON reducido, STATS sin M2, stage factors elegidos y por qué

2. **Actualizar `RecalculateScoresUseCase`**
   - STATS events: `combined = max(0.3, min(4.0, M1 * 1.0))` — sin M2
   - GOAL/ASSIST events: usar `get_stage_factor()` del repo para M2 real
   - Asegurar que usa `BASE_POINTS_TABLE` actualizado (import desde services.py)

3. **Limpiar root del proyecto**
   - Borrar o mover los scripts standalone a `scripts/` con un README explicativo
   - El `recalculate_all_scores.py` debería ser un Celery task o endpoint admin

4. **Verificar Wikipedia backfill**
   - Si incompleto, relanzar `backfill_wikipedia_photos.py`
   - Considerar convertir en Celery task para ejecutar periódicamente

---

---

## 1. Implementar archivos .http faltantes y probar flujo completo

Crear `http/admin.http` con todos los endpoints de admin, y verificar que el
flujo completo de ingesta funciona end-to-end.

**Archivos .http existentes:**
- `http/ranking.http` ✓
- `http/players.http` ✓
- `http/competitions.http` ✓
- `http/compare.http` ✓
- `http/status.http` ✓

**Pendiente crear:**
- [ ] `http/admin.http` — todos los endpoints `POST /admin/*`:
  - `POST /admin/ingest/{league_id}`
  - `POST /admin/ingest-all`
  - `POST /admin/enrich-fbref/{competition_id}`
  - `POST /admin/enrich-understat/{competition_id}`
  - `POST /admin/enrich-all`
  - `POST /admin/recalculate/{competition_id}`
  - `GET /admin/ingestion-logs`

**Flujo completo a probar:**
- [ ] Levantar stack con Docker Compose
- [ ] Correr migraciones
- [ ] `POST /admin/ingest/140` (La Liga, season=2024)
- [ ] Verificar datos en `GET /ranking`
- [ ] `POST /admin/enrich-fbref/1?competition_name=La+Liga&season=2024`
- [ ] `POST /admin/enrich-understat/1?competition_name=La+Liga&season=2024&season_int=2024`
- [ ] Verificar que los scores cambiaron en `GET /players/{id}/events`

---

## 2. Implementar Swagger / OpenAPI

- Configurar FastAPI para generar documentación OpenAPI automática
- Añadir `response_model`, descripciones y ejemplos en cada endpoint
- Validar que los schemas en `api/v1/schemas/` estén completos
- Exponer `/docs` y `/redoc` en entorno de desarrollo

---

## 3. UI en React (post-optimización backend)

Una vez el backend esté estable y optimizado:
- Scaffoldear proyecto React (Vite)
- Implementar vistas: Ranking, Detalle de jugador, Comparador
- Conectar con la API del backend
- Deploy coordinado con Docker Compose

---

## 4. Auditoría de Variables Hardcodeadas

Rastrear todas las variables con valores fijos en el código y evaluar cada una:
- `KNOWN_POSITIONS` (`domain/position_mapping.py`) — lista manual de jugadores
- `BASE_POINTS_TABLE` (`domain/scoring/services.py`) — tabla de puntos por posición/acción
- `LEAGUES` (`use_cases/ingest_competition.py`) — lista de ligas con IDs y factores
- `ROUND_TO_STAGE` — mapeo de rondas de Champions a instancias SFA
- Factores de competición (`comp_factor`, `stage_factor`)

Para cada variable determinar:
- [ ] ¿Tiene sentido hardcodeada? (cambia poco, es config de negocio)
- [ ] ¿Mejora con BD? (cambia frecuentemente, depende de datos externos)
- [ ] ¿Es peligrosa hardcodeada? (puede causar errores silenciosos o scoring incorrecto)

RECOMENDACION: Usar un LLM o alguna herramienta de busqueda para indagar o clasificar la posicion de ciertos jugadores
o usar tavily search
