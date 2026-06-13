# SFA — Stadistic Football Award: Contexto del Proyecto

> Documento de contexto para Claude / LLMs. **Última actualización: 2026-06-07.**
> Complementa `backend/CLAUDE.md` (arquitectura y convenciones técnicas).
> Este archivo cubre: qué es el proyecto, estado actual, bugs conocidos, decisiones tomadas y pendientes.

---

## ¿Qué es SFA?

Sistema de puntuación de jugadores de fútbol que reemplaza las estadísticas crudas (goles, asistencias) con un **score contextualizado (SFA pts)**. Cada acción significativa de un jugador vale puntos base multiplicados por factores de contexto.

### Multiplicadores (v2 — activos en rules_version_id=3)

| Multiplicador | Qué mide | Aplica a |
|---|---|---|
| **M1** | Dificultad del rival (ELO normalizado cuando disponible, fallback posición de liga) | Goles/asistencias: M1 completo. Stats acumulativas: M1 suavizado (weight=0.35, clamp 0.85–1.20) |
| **M2** | Fase de la competición (stage_factor) | Goles, asistencias, midfield bonuses |
| **M3** | Minuto del partido + marcador | Solo goles y asistencias (eventos individuales) |
| **M4** | Dificultad del disparo / PSxG | Solo goles (M4=1.0 actualmente — PSxG no poblado) |
| **Mvisit** | Bonus por jugar fuera de casa | Solo goles y asistencias |
| **Mrating** | Rating API-Football del jugador en el partido | Stats acumulativas |
| **competition_weight** | Peso de la competición (CL=1.0, EL=0.75, copas=0.25-0.65) | **TODAS las stats** (desde sesión 2026-06-07) |

**Fórmulas v2 (actualizadas):**
```
# Goles / asistencias (eventos individuales):
SFA pts = base × clamp(M1 × M2 × M3 × M4 × Mvisit, 0.3, 4.0)

# Stats acumulativas por partido:
M1_stats = clamp(1.0 + (M1 - 1.0) × 0.35, 0.85, 1.20)
SFA pts = base_total × competition_weight × clamp(M1_stats × M2 × Mrating, 0.3, 4.0)
# ↑ competition_weight ahora aplica a TODAS las stats (no solo MC bonuses)

# Midfield bonuses (MC y MCO, no usan M1):
mc_bonus_final = mc_bonus_base × M2 × Mrating × competition_weight
```

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async (asyncpg) |
| Base de datos | PostgreSQL 16 |
| Cola de tareas | Celery 5 + Redis 7 |
| Infraestructura | Docker Compose (dev) |
| Fuentes de datos | API-Football v3 (principal), ClubElo (team ELO), Transfermarkt (posiciones) |
| Frontend | React + TypeScript + Vite (proxy → localhost:8000) |

**Correr frontend:** desde **Windows PowerShell** (NO desde WSL — node_modules son nativos Windows):
```powershell
cd C:\Users\formu\OneDrive\Escritorio\sfa-project\frontend
npm run dev
```

---

## Arquitectura

Hexagonal estricta. Todo flujo sigue:
```
Router (FastAPI) → Use Case → Repository (SQLAlchemy) → PostgreSQL
```

- **`api/v1/`** — routers + Pydantic schemas
- **`application/use_cases/`** — lógica de negocio
- **`domain/`** — protocolos, DTOs frozen, scoring
- **`infrastructure/`** — repositorios, proveedores, modelos SQLAlchemy
- **`core/dependencies.py`** — único lugar de wiring (DI)
- **`tasks/`** — Celery tasks como wrappers async

---

## Grupos de posición (v2 — actualizado 2026-06-07)

| Grupo | Posiciones | Descripción |
|---|---|---|
| `DEL` | Delanteros | Striker / 9 |
| `EXT` | Extremos | Winger / Second striker |
| `MCO` | MC ofensivo | Attacking Midfield (Bruno, Bellingham, Ødegaard) — **NUEVO** |
| `MF` / `MC` | MC puro | Box-to-box / Central Midfield (Vitinha, Rodri) |
| `LAT` | Laterales | Full-back |
| `DC` | Defensas centrales | Center-back |
| `FW` | deprecated | Alias legacy de DEL+EXT (v1) |
| `DF` | deprecated | Alias legacy de DC+LAT (v1) |

**Fuente de posiciones:** Transfermarkt (prioritaria) > API-Football (fallback).
Campo `position_source` en tabla `players` indica el origen. Si es `'transfermarkt'`, no se sobreescribe en ingestas futuras.

---

## Tabla de puntos base v2 — BASE_POINTS_TABLE_V2

Fuente: `backend/src/sfa/domain/scoring/value_objects.py`

| Acción | DEL | EXT | **MCO** | MC | LAT | DC |
|---|---:|---:|---:|---:|---:|---:|
| Gol | 500 | 550 | **600** | 700 | 750 | 850 |
| Gol penalti | 300 | 320 | **310** | 380 | 390 | 400 |
| Asistencia | 500 | 520 | **520** | 520 | 580 | 640 |
| Pases completados (base/pts) | 2 | 2 | **2** | 5 | 1 | 1 |
| Pases threshold | 20 | 28 | **45** | 50 | 38 | 32 |
| Regate ganado | 100 | 120 | **110** | 100 | 110 | 130 |
| Duelo ganado | 30 | 28 | **10** | 12 | 22 | 25 |
| Tackle | 110 | 105 | **55** | 70 | 130 | 150 |
| Intercepciones | 90 | 85 | **70** | 95 | 160 | 200 |
| Blocks | 150 | 130 | **90** | 100 | 120 | 130 |
| Pases clave (xa) | 60 | 70 | **90** | 85 | 65 | 80 |
| xG sin gol | 70 | 65 | **70** | 50 | 35 | 30 |
| Faltas recibidas | 50 | 45 | **35** | 25 | 25 | 20 |
| Penal ganado | 200 | 190 | **180** | 180 | 100 | 80 |
| Faltas cometidas | −30 | −25 | **−25** | −20 | −20 | −15 |
| Tarjeta amarilla | −150 | −150 | **−150** | −150 | −150 | −150 |
| Tarjeta roja | −500 | −500 | **−500** | −500 | −500 | −500 |
| Regates sufridos | 0 | −10 | **−15** | −20 | −30 | −50 |

**PASSES_COMPLETED:** solo puntúan los pases POR ENCIMA del threshold por posición.
**IMPORTANTE:** `passes_accuracy` en API-Football = conteo de pases completados (no porcentaje).

---

## Midfield Control Bonuses (spec 0014, MC y MCO)

Bonuses adicionales para midfielders con rendimiento excepcional en un partido (≥60 min):

| Bonus | Condición | Base pts |
|---|---|---|
| CONTROL | passes_completed ≥ 65, accuracy ≥ 90%, rating ≥ 7.6 | 140 |
| TWO_WAY | passes_completed ≥ 50, defensive ≥ 3, rating ≥ 7.4 | 90 |
| CREATIVE | passes_completed ≥ 55, accuracy ≥ 85%, key_passes ≥ 2, rating ≥ 7.7 | 70 |

Cap por partido: **180 pts**. Fórmula: `base × M2 × Mrating × competition_weight`.

---

## Achievement Bonuses

Bonuses por logros en competición:

```
achievement_bonus = bonus_base × competition_weight × participation_ratio × performance_factor
```

- `participation_ratio = player_minutes / (competition_fixtures × 90)`
- `performance_factor = clamp(rank_factor × rating_factor, 0.50, 1.35)`

**Valores UCL en DB (corregidos 2026-06-07):**

| Fase | Bonus base | Weight |
|---|---|---|
| winner | **10,000** | 1.0 |
| semi_final | **5,000** | 1.0 |
| quarter_final | **3,000** | 1.0 |
| round_of_16 | **1,500** | 1.0 |

Ligas domésticas: champion=7,000, runner_up=2,500, top_4=1,000 (sin cambios).

---

## ELO de equipos (spec 0017)

Team strength basado en ELO (ClubElo) en lugar de posición en tabla.

```
# Seed inicial (una vez por temporada):
POST /api/v1/admin/elo/seed
  { "date_str": "2024-08-01", "season": "2024" }

# Recalcular ELO con fixtures de la temporada:
POST /api/v1/admin/elo/recalculate
  { "season": "2024", "competition_ids": [...], "k_factors": {"10": 35}, "default_k": 30.0 }
```

- ELO normalizado: `(elo - 1400) / 700 * 100` → escala 0-100 compatible con M1
- Columna `elo_raw` en `team_strengths` guarda el ELO bruto
- K-factors: CL/EL=35, ligas domésticas=30, copas=25
- Auto-update: se dispara `apply_elo_update_task` después de cada ingesta

---

## Posiciones desde Transfermarkt (spec 0019)

```
# Lanzar enrich batch (~6000 jugadores, ~90-120 min):
POST /api/v1/admin/players/enrich-positions
  { "season": "2024", "dry_run": false, "batch_size": 500 }
```

- Rate limit: 1 req/seg a Transfermarkt
- Tabla `player_tm_ids` guarda el Transfermarkt ID de cada jugador
- `position_source = 'transfermarkt'` → inmutable ante futuras ingestas API-Football
- Mapping: "Attacking Midfield"→MCO, "Centre-Back"→DC, "Right/Left-Back"→LAT, etc.

---

## Pipeline de datos

### Ingesta (API-Football)
```
POST /api/v1/admin/ingest/{league_id}?season=YYYY
  → standings → fixtures → events + player_stats
  → upsert: players (respeta position_source='transfermarkt'), teams, fixtures
  → auto-dispara: apply_elo_update_task
```

### Recalculación completa (endpoint unificado — spec 0016)
```
POST /api/v1/scoring/recalculate-full
  { "rules_version_id": 3, "season": "2024", "force_recalculate": true }
  → scoring de 92k eventos (bulk SQL, ~3-5 min)
  → achievement bonuses para todas las competiciones
```

---

## ScoringRulesVersion en BD

| id | name | activa | Notas |
|---|---|---|---|
| 2 | v1.0-initial | ✓ | Config v1 (grupos FW/MF/DF, sin midfield bonuses) |
| 3 | v2.0-impact-model | — | Config v2 con MCO, ELO M1, competition_weight en stats — usar para ranking |

El frontend usa `rules_version_id=3` + `use_total=true`.

---

## Estado actual de los datos (temporada 2024, junio 2026)

| Competición | ID | Estado |
|---|---|---|
| La Liga | 1 | Completa |
| Premier League | 3 | Completa |
| Bundesliga | 6 | Completa |
| Serie A | 7 | Completa |
| Ligue 1 | 9 | Completa |
| Champions League | 10 | Completa |
| Copa del Rey | 22 | Completa |
| Supercopa de España | 23 | Completa |
| FA Cup | 90 | Completa |
| DFB-Pokal | 92 | Completa |
| Coppa Italia | 94 | Completa |
| Coupe de France | 96 | Completa |
| Europa League | 253 | Completa |
| Conference League | 254 | Completa |
| EFL Cup | 256 | Completa |
| Community Shield | 257 | Completa |
| DFL-Supercup | 258 | Completa |
| Supercoppa Italiana | 259 | Completa |
| Trophée des Champions | 260 | Completa |

**Totales:** ~92,700 eventos, ~10,896 jugadores, 19 competiciones.
**API-Football:** plan real = 7,500 req/día.

### Distribución de posiciones en players (post spec 0018)
```
MC:   5,837  (incluye MCO pendientes de enrich Transfermarkt)
GK:     478  ✅ corregidos
DC:     412  ✅ corregidos
EXT:     90
DEL:     78
LAT:     34  (pendiente de enrich Transfermarkt para corregir ~726 laterales)
MCO:      0  (se poblarán tras el enrich)
```

---

## Cambios de scoring sesión 2026-06-07

### 1. competition_weight aplicado a TODAS las stats
**Archivo:** `calculate_scores_for_rules_version.py` → `_score_stats_event()`
```python
# Antes:
final = round(base_total, 2)
# Ahora:
final = round(base_total * competition_weight, 2)
```
**Impacto:** stats de Bruno en EL (×0.75), copas (×0.25-0.65) pierden valor. UCL (×1.0) sin cambio.

### 2. UCL bonus values corregidos en DB
Winner: 3,500 → **10,000**. Semi: 2,000 → **5,000**. QF: 1,500 → **3,000**. R16: 1,000 → **1,500**.

### 3. Posición MCO agregada al dominio de scoring
Nueva posición en enum + PositionGroup + BASE_POINTS_TABLE_V2 (ver tabla arriba).

### 4. Bugs corregidos en pipeline de recalculación (spec 0016)
- Bulk SQL en season score rebuild (de ~21,000 queries a 1)
- Fix double-computation en achievement bonuses
- Endpoint unificado `POST /scoring/recalculate-full`
- Bug: `CAST(:now_ts AS TIMESTAMPTZ)` → `NOW()` (asyncpg no aceptaba string ISO)

---

## Specs implementados (sesión 2026-06-07)

| Spec | Descripción | Estado |
|---|---|---|
| 0016 (feature) | Full recalculation pipeline | ✅ implementado |
| 0016 (refactor) | Bulk season score rebuild | ✅ implementado |
| 0017 (feature) | ELO team ratings con seed ClubElo | ✅ implementado |
| 0018 (refactor) | Position mapping fix (GK/DC heurísticas) | ✅ implementado |
| 0019 (feature) | Transfermarkt position enrichment + MCO | ✅ implementado, enrich pendiente |

---

## Fuentes de datos activas vs descartadas

| Fuente | Estado | Uso |
|---|---|---|
| API-Football v3 | ✅ activa | Ingesta principal (stats, eventos, fixtures) |
| ClubElo | ✅ activa | Team ELO para M1 |
| Transfermarkt | ✅ activa | Sub-posiciones de jugadores |
| FBref | ❌ roto (2025) | HTML cambió, scraper no funciona |
| Understat | ⚠️ parcial | Solo totales de temporada, no per-shot — insuficiente para M4 |
| StatsBomb / Opta | ❌ de pago | Necesario para M4 real (PSxG por disparo) |

---

## Tareas pendientes

### Alta — recálculo definitivo
- [ ] **Esperar fin del enrich Transfermarkt** (~90-120 min, Celery corriendo)
- [ ] **Verificar MCO players**: `SELECT position, COUNT(*) FROM players GROUP BY position`
      — MCO y LAT deben haber aumentado significativamente
- [ ] **Recálculo definitivo**: `POST /scoring/recalculate-full {"rules_version_id":3,"season":"2024","force_recalculate":true}`
- [ ] **Ver ranking final** y decidir si arrancamos con el frontend

### Media
- [ ] **RecalculateScoresUseCase legacy** — decidir si eliminar o migrar a v2
- [ ] **Equipos (`/teams`)** — módulo pendiente (ruta placeholder)
- [ ] **`AdvancedStatsBar.tsx`** — archivo huérfano en frontend, eliminar
- [ ] **Activar M4** — requiere fuente con PSxG por disparo (StatsBomb/Opta, de pago)

### Baja
- [ ] **Scripts standalone en root** — violan arquitectura, limpiar
- [ ] **Deploy** — frontend + backend juntos en Docker para producción

---

## Problemas conocidos

### Enrich Transfermarkt limitado por rate limiting
El enrich de 6,000 jugadores a 1 req/seg toma ~90-120 min. Si Transfermarkt bloquea, el task fallará parcialmente. Los jugadores no matcheados quedan con position_source='apifootball'.

### LAT sigue bajo (~34) hasta que termine el enrich
Los laterales de las 19 competiciones son difíciles de distinguir de MC por heurísticas. Transfermarkt los clasifica correctamente como "Right-Back"/"Left-Back". Solo después del enrich estarán corregidos.

### M4 desactivado (PSxG=1.0 para todos los goles)
M4 está implementado pero sin datos reales. Requiere PSxG por disparo individual, que solo proveen fuentes de pago.

### Docker — red sin asignar en arranque fresco
```bash
docker network connect backend_default backend-db-1
docker network connect backend_default backend-redis-1
docker restart backend-api-1 backend-celery_worker-1 backend-celery_beat-1
```

---

## Workflow para nuevas features

**NUNCA implementar sin spec.** El flujo es:
```
1. Solicitud → invocar @Architecture-Engineer
2. @Architecture-Engineer → /sfa-spec → specs/NNNN-slug/
3. Implementación siguiendo plan.md completo
```

---

## Cómo levantar el proyecto

```bash
# Backend (WSL)
cd /mnt/c/Users/formu/OneDrive/Escritorio/sfa-project/backend
docker compose -f docker-compose-development.yml up -d

# Verificar
curl http://localhost:8000/api/v1/health

# Frontend (Windows PowerShell — NO WSL)
cd C:\Users\formu\OneDrive\Escritorio\sfa-project\frontend
npm run dev
# → http://localhost:5173
```

---

## Archivos clave

```
sfa-project/
├── PROJECT-CONTEXT.md              ← este archivo (leer primero)
├── backend/
│   ├── CLAUDE.md                   ← arquitectura, convenciones (leer siempre)
│   ├── CODEX-RECALC-PLAN.md        ← plan detallado de implementación 0016 (referencia)
│   ├── specs/
│   │   ├── feature/0016-full-recalculation-pipeline/
│   │   ├── feature/0017-elo-team-ratings/
│   │   ├── feature/0019-transfermarkt-position-enrichment/
│   │   ├── refactor/0016-bulk-season-score-rebuild/
│   │   └── refactor/0018-position-mapping-fix/
│   ├── migrations/                 ← SQL plano (0012-0016)
│   ├── http/                       ← archivos .http para probar endpoints
│   └── src/sfa/
│       ├── domain/scoring/
│       │   ├── value_objects.py    ← ScoringConfig, MCO base_points, ELO norm
│       │   └── services.py         ← BASE_POINTS_TABLE_V2 (con MCO)
│       ├── infrastructure/
│       │   ├── providers/
│       │   │   ├── clubelo_provider.py       ← ELO seed
│       │   │   └── transfermarkt_scraper.py  ← posiciones sub-tipo
│       │   ├── models/
│       │   │   ├── team_strengths/models.py  ← campo elo_raw
│       │   │   └── players/models.py         ← campo position_source
│       │   └── repositories/
│       │       ├── player_event_score_repository.py  ← bulk_rebuild_season_scores
│       │       └── team_strength_repository.py       ← get_fixtures_for_elo_recalc
│       ├── application/use_cases/
│       │   ├── calculate_scores_for_rules_version.py  ← competition_weight en stats
│       │   ├── run_full_recalculation.py              ← orquestador principal
│       │   ├── seed_clubelo.py                        ← ELO seed use case
│       │   ├── calculate_elo_ratings.py               ← ELO recalc use case
│       │   └── enrich_player_positions.py             ← Transfermarkt batch
│       └── tasks/
│           ├── run_full_recalculation_task.py
│           ├── elo_tasks.py
│           └── enrich_player_positions_task.py
└── frontend/
    └── src/
        ├── api/client.ts           ← rules_version_id=3, use_total=true
        └── components/player/
            ├── PointsBreakdown.tsx
            └── HighlightsView.tsx
```
