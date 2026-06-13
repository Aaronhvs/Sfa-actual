# Plan: 0012 — Add Missing Competitions + Fix Cup Stages

**Feature branch:** `feat/0012-add-missing-competitions`
**Spec date:** 2026-06-01
**Scope:** Migración SQL (stages + nuevas competiciones) + registro de league_ids en LEAGUES.

---

## Archivos a crear

- [ ] `backend/migrations/0014_add_missing_competitions.sql` — Inserta `competition_stages`
  para las 4 copas existentes sin stages; inserta las 8 nuevas competiciones con sus
  `competition_stages`.

## Archivos a modificar

- [ ] `backend/src/sfa/application/use_cases/ingest_competition.py` — Añadir 8 nuevas
  entradas `LeagueConfig` a la lista `LEAGUES`.

---

## Checklist de implementación

### Paso 1 — Crear migración SQL `0014_add_missing_competitions.sql`

Crear el archivo `backend/migrations/0014_add_missing_competitions.sql` con el siguiente
contenido exacto:

```sql
-- Migration 0014: Add missing competitions + fix competition_stages for existing cups
-- Applies: 2026-06-01
-- Spec: specs/feature/0012-add-missing-competitions/

BEGIN;

-- ─── PARTE A: competition_stages para las 4 copas existentes ─────────────────
-- Estas competiciones ya tienen fixtures pero sus stages nunca fueron insertados.
-- El INSERT usa ON CONFLICT DO NOTHING para idempotencia.

INSERT INTO competition_stages (competition_id, stage, stage_factor)
SELECT c.id, s.stage, s.stage_factor
FROM competitions c
JOIN (VALUES
    ('FA Cup',          'regular', 1.00),
    ('FA Cup',          'quarter', 1.20),
    ('FA Cup',          'semi',    1.30),
    ('FA Cup',          'final',   1.50),
    ('DFB-Pokal',       'regular',      1.00),
    ('DFB-Pokal',       'round_of_16',  1.10),
    ('DFB-Pokal',       'quarter',      1.20),
    ('DFB-Pokal',       'semi',         1.30),
    ('DFB-Pokal',       'final',        1.50),
    ('Coppa Italia',    'regular',      1.00),
    ('Coppa Italia',    'round_of_16',  1.10),
    ('Coppa Italia',    'quarter',      1.20),
    ('Coppa Italia',    'semi',         1.30),
    ('Coppa Italia',    'final',        1.50),
    ('Coupe de France', 'regular',      1.00),
    ('Coupe de France', 'round_of_16',  1.10),
    ('Coupe de France', 'quarter',      1.20),
    ('Coupe de France', 'semi',         1.30),
    ('Coupe de France', 'final',        1.50)
) AS s(comp_name, stage, stage_factor) ON c.name = s.comp_name
ON CONFLICT ON CONSTRAINT uq_competition_stage DO NOTHING;


-- ─── PARTE B: Insertar las 8 nuevas competiciones ────────────────────────────

INSERT INTO competitions (name, country, competition_factor) VALUES
    ('Europa League',          'EUR', 1.20),
    ('Conference League',      'EUR', 1.00),
    ('UEFA Super Cup',         'EUR', 1.10),
    ('EFL Cup',                'ENG', 0.90),
    ('Community Shield',       'ENG', 0.80),
    ('DFL-Supercup',           'GER', 0.90),
    ('Supercoppa Italiana',    'ITA', 0.90),
    ('Trophée des Champions',  'FRA', 0.85)
ON CONFLICT (name) DO UPDATE
    SET country            = EXCLUDED.country,
        competition_factor = EXCLUDED.competition_factor;


-- ─── PARTE C: competition_stages para las 8 nuevas competiciones ─────────────

INSERT INTO competition_stages (competition_id, stage, stage_factor)
SELECT c.id, s.stage, s.stage_factor
FROM competitions c
JOIN (VALUES
    -- Europa League — mismo formato UEFA que Champions League
    ('Europa League', 'group',       1.50),
    ('Europa League', 'regular',     1.50),
    ('Europa League', 'round_of_16', 1.80),
    ('Europa League', 'quarter',     2.00),
    ('Europa League', 'semi',        2.30),
    ('Europa League', 'final',       2.80),
    -- Conference League — mismo formato UEFA
    ('Conference League', 'group',       1.50),
    ('Conference League', 'regular',     1.50),
    ('Conference League', 'round_of_16', 1.80),
    ('Conference League', 'quarter',     2.00),
    ('Conference League', 'semi',        2.30),
    ('Conference League', 'final',       2.80),
    -- UEFA Super Cup — partido único
    ('UEFA Super Cup', 'final', 2.00),
    -- EFL Cup — formato copa nacional inglesa
    ('EFL Cup', 'regular', 1.00),
    ('EFL Cup', 'quarter', 1.20),
    ('EFL Cup', 'semi',    1.30),
    ('EFL Cup', 'final',   1.50),
    -- Community Shield — partido único de menor prestige
    ('Community Shield', 'final', 1.20),
    -- DFL-Supercup — partido único
    ('DFL-Supercup', 'final', 1.20),
    -- Supercoppa Italiana — formato con semifinales (igual que Supercopa de España)
    ('Supercoppa Italiana', 'semi',  1.10),
    ('Supercoppa Italiana', 'final', 1.30),
    -- Trophée des Champions — partido único
    ('Trophée des Champions', 'final', 1.10)
) AS s(comp_name, stage, stage_factor) ON c.name = s.comp_name
ON CONFLICT ON CONSTRAINT uq_competition_stage DO NOTHING;

COMMIT;
```

**Verificación SQL tras aplicar:**
```sql
-- Debe devolver filas para las 4 copas existentes
SELECT c.name, cs.stage, cs.stage_factor
FROM competition_stages cs
JOIN competitions c ON c.id = cs.competition_id
WHERE c.name IN ('FA Cup', 'DFB-Pokal', 'Coppa Italia', 'Coupe de France')
ORDER BY c.name, cs.stage_factor;

-- Debe devolver las 8 nuevas competiciones
SELECT name, country, competition_factor FROM competitions
WHERE name IN (
    'Europa League', 'Conference League', 'UEFA Super Cup',
    'EFL Cup', 'Community Shield', 'DFL-Supercup',
    'Supercoppa Italiana', 'Trophée des Champions'
)
ORDER BY name;

-- Conteo total de stages por competición
SELECT c.name, COUNT(cs.id) as num_stages
FROM competitions c
LEFT JOIN competition_stages cs ON cs.competition_id = c.id
GROUP BY c.name
ORDER BY c.name;
```

---

### Paso 2 — Aplicar la migración en la base de datos

```bash
psql $DATABASE_URL -f backend/migrations/0014_add_missing_competitions.sql
```

Verificar que el script termina con `COMMIT` sin errores. Si ya fue aplicada
parcialmente, la cláusula `ON CONFLICT DO NOTHING` / `DO UPDATE` garantiza idempotencia.

---

### Paso 3 — Añadir 8 entradas a `LEAGUES` en `ingest_competition.py`

**Archivo:** `backend/src/sfa/application/use_cases/ingest_competition.py`

Localizar el bloque `LEAGUES: list[LeagueConfig] = [...]` y añadir al final, después de
la entrada de `Coupe de France`:

```python
    # ── Europa League ───────────────────────────────────────────────────────
    LeagueConfig(id=3,   name="Europa League",          country="EUR", comp_factor=1.2),
    # ── Conference League ───────────────────────────────────────────────────
    LeagueConfig(id=848, name="Conference League",      country="EUR", comp_factor=1.0),
    # ── EFL Cup ─────────────────────────────────────────────────────────────
    LeagueConfig(id=48,  name="EFL Cup",                country="ENG", comp_factor=0.9,  standings_league_id=39),
    # ── Supercoppa Italiana ─────────────────────────────────────────────────
    LeagueConfig(id=547, name="Supercoppa Italiana",    country="ITA", comp_factor=0.9,  standings_league_id=135),
    # ── DFL-Supercup ────────────────────────────────────────────────────────
    LeagueConfig(id=529, name="DFL-Supercup",           country="GER", comp_factor=0.9,  standings_league_id=78),
    # ── Trophée des Champions ───────────────────────────────────────────────
    LeagueConfig(id=526, name="Trophée des Champions",  country="FRA", comp_factor=0.85, standings_league_id=61),
    # ── Community Shield ────────────────────────────────────────────────────
    LeagueConfig(id=528, name="Community Shield",       country="ENG", comp_factor=0.8,  standings_league_id=39),
    # ── UEFA Super Cup ──────────────────────────────────────────────────────
    LeagueConfig(id=531, name="UEFA Super Cup",         country="EUR", comp_factor=1.1,  standings_league_id=2),
]
```

**Notas de implementación:**
- El orden en `LEAGUES` determina la prioridad de ingestión cuando se alcanza el límite
  de 7 000 peticiones. Europa League y Conference League van primero por mayor volumen
  de jugadores relevantes.
- `standings_league_id=2` para UEFA Super Cup hace que el use case tome los standings
  de Champions League para calcular M1. Como el partido enfrenta al campeón de CL vs
  al campeón de EL, ambos equipos estarán en esos standings (o en los de Europa League).
- `comp_factor=1.2` para Europa League: valor `float` que el use case pasa a
  `upsert_competition`; debe coincidir con el `competition_factor=1.20` insertado en la
  migración (la columna NUMERIC(4,2) redondea, no trunca).

---

### Paso 4 — Re-ingerir las 4 copas existentes para corregir M2 histórico

Una vez aplicada la migración (Paso 2), disparar re-ingestión para cada copa. Esto
reescribirá los `player_events` con los valores M2 correctos según los stages ahora
presentes en DB.

**Vía API (endpoint admin):**
```bash
curl -X POST "http://localhost:8000/api/v1/admin/ingest/45?season=2024"   # FA Cup
curl -X POST "http://localhost:8000/api/v1/admin/ingest/81?season=2024"   # DFB-Pokal
curl -X POST "http://localhost:8000/api/v1/admin/ingest/137?season=2024"  # Coppa Italia
curl -X POST "http://localhost:8000/api/v1/admin/ingest/66?season=2024"   # Coupe de France
```

**Vía Celery shell (alternativa):**
```python
from sfa.tasks.ingestion_tasks import ingest_competition_task
ingest_competition_task.delay(45, 2024)   # FA Cup
ingest_competition_task.delay(81, 2024)   # DFB-Pokal
ingest_competition_task.delay(137, 2024)  # Coppa Italia
ingest_competition_task.delay(66, 2024)   # Coupe de France
```

Cada task re-ingestará los fixtures ya conocidos, borrará los `player_events` obsoletos
por fixture (`delete_player_events_for_fixture`) y los reescribirá con M2 correcto.
No consumirá standings (ya cacheados en DB) pero sí fixtures/events/players de
API-Football. **Coste estimado: ~50–80 requests por copa**, dependiendo del número de
fixtures y equipos procesados en temporada 2024.

---

### Paso 5 — Disparar ingestión inicial para las 8 nuevas competiciones

```bash
# Vía ingest-all (procesará en orden de LEAGUES, respetando el guard de 7000 req)
curl -X POST "http://localhost:8000/api/v1/admin/ingest-all?season=2024"

# Alternativa: ingestión individual por competición
curl -X POST "http://localhost:8000/api/v1/admin/ingest/3?season=2024"    # Europa League
curl -X POST "http://localhost:8000/api/v1/admin/ingest/848?season=2024"  # Conference League
curl -X POST "http://localhost:8000/api/v1/admin/ingest/48?season=2024"   # EFL Cup
curl -X POST "http://localhost:8000/api/v1/admin/ingest/547?season=2024"  # Supercoppa Italiana
curl -X POST "http://localhost:8000/api/v1/admin/ingest/529?season=2024"  # DFL-Supercup
curl -X POST "http://localhost:8000/api/v1/admin/ingest/526?season=2024"  # Trophée des Champions
curl -X POST "http://localhost:8000/api/v1/admin/ingest/528?season=2024"  # Community Shield
curl -X POST "http://localhost:8000/api/v1/admin/ingest/531?season=2024"  # UEFA Super Cup
```

**Nota para UEFA Super Cup:** El use case intentará `fetch_standings(2, 2024)` (CL
standings prestados). Si devuelve equipos, procesará los fixtures de league_id=531 para
los dos equipos que disputaron la final. Si devuelve lista vacía, el use case retornará
`IngestionResult` con `status="completed"` y `fixtures_processed=0` sin error.

---

### Paso 6 — Verificar ingestión y scores

```sql
-- Verificar que las nuevas competiciones tienen fixtures
SELECT c.name, COUNT(f.id) as fixtures, f.season
FROM competitions c
JOIN fixtures f ON f.competition_id = c.id
WHERE c.name IN (
    'Europa League', 'Conference League', 'UEFA Super Cup',
    'EFL Cup', 'Community Shield', 'DFL-Supercup',
    'Supercoppa Italiana', 'Trophée des Champions'
)
GROUP BY c.name, f.season
ORDER BY c.name;

-- Verificar que los stages se están usando (m2 > 1.0 para partidos de eliminatoria)
SELECT c.name, f.stage, pe.m2, COUNT(*) as events
FROM player_events pe
JOIN fixtures f ON f.id = pe.fixture_id
JOIN competitions c ON c.id = f.competition_id
WHERE c.name IN ('FA Cup', 'DFB-Pokal', 'Coppa Italia', 'Coupe de France')
  AND f.stage != 'regular'
GROUP BY c.name, f.stage, pe.m2
ORDER BY c.name, pe.m2 DESC;
-- Esperado: m2 > 1.0 para quarter/semi/final (1.20, 1.30, 1.50)

-- Verificar scores calculados tras re-ingestión
SELECT c.name, COUNT(DISTINCT ss.player_id) as players_scored, AVG(ss.total_pts) as avg_pts
FROM sfa_season_scores ss
JOIN competitions c ON c.id = ss.competition_id
WHERE ss.season = '2024'
  AND c.name IN ('FA Cup', 'DFB-Pokal', 'Coppa Italia', 'Coupe de France',
                 'Europa League', 'Conference League')
GROUP BY c.name
ORDER BY c.name;
```

---

## Agent Routing Brief

**DDD Designer needed:** no

Esta feature no introduce nuevas entidades de dominio. Los cambios son:
1. Datos de configuración en DB (filas en `competition_stages` y `competitions`).
2. Configuración de aplicación en `LEAGUES` (lista de `LeagueConfig` ya existente).
3. No se crean nuevos value objects, puertos, use cases ni repositorios.

El modelo de dominio existente (`Competition`, `CompetitionStage`, `LeagueConfig`) ya
soporta todas las nuevas entidades sin modificación alguna.

---

## Verificación end-to-end

1. **Migración aplicada correctamente:**
   ```sql
   SELECT COUNT(*) FROM competition_stages; -- debe ser ≥ 19 (antes eran 0 para las 4 copas)
   SELECT COUNT(*) FROM competitions;       -- debe ser 20
   ```

2. **LEAGUES lista actualizada:**
   ```python
   from sfa.application.use_cases.ingest_competition import LEAGUES
   assert len(LEAGUES) == 20
   assert any(l.id == 3 and l.name == "Europa League" for l in LEAGUES)
   assert any(l.id == 848 and l.name == "Conference League" for l in LEAGUES)
   ```

3. **M2 corregido para copas existentes** (tras re-ingestión del Paso 4):
   ```sql
   SELECT DISTINCT f.stage, pe.m2
   FROM player_events pe
   JOIN fixtures f ON pe.fixture_id = f.id
   JOIN competitions c ON f.competition_id = c.id
   WHERE c.name = 'FA Cup' AND f.season = '2024'
   ORDER BY pe.m2;
   -- Esperado: final→m2=1.50, semi→m2=1.30, quarter→m2=1.20, regular→m2=1.00
   ```

4. **Ingestión Europa League produce datos:**
   ```sql
   SELECT COUNT(*) FROM fixtures f
   JOIN competitions c ON c.id = f.competition_id
   WHERE c.name = 'Europa League' AND f.season = '2024';
   -- Esperado: > 0
   ```

5. **`ingest-all` no explota el quota:**
   Ejecutar `ingest-all` y verificar que el log de Celery muestra
   `requests_used < 7000` al finalizar.
