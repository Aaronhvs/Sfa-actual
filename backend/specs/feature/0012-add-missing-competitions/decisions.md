# 0012 — Add Missing Competitions

## Contexto

El sistema tiene 12 competiciones. El objetivo son 20 (5 ligas + 8 copas/supercopas nacionales + 3 UEFA + 4 supercopas). Dos problemas detectados:

1. **4 copas existentes sin `competition_stages`**: FA Cup, DFB-Pokal, Coppa Italia, Coupe de France tienen fixtures ingresados pero el JOIN en `get_events_for_recalc` las excluye del scoring v2 porque no tienen stages.
2. **8 competiciones faltantes**: Europa League, Conference League, UEFA Super Cup, EFL Cup, Community Shield, DFL-Supercup, Supercoppa Italiana, Trophée des Champions.

---

## Decisiones

### D1 — SQL idempotente, sin migración Alembic

Las inserciones usan `ON CONFLICT DO NOTHING`. No hay schema changes (no nuevas columnas), solo datos de referencia. Se ejecuta directo contra la DB de desarrollo.

### D2 — stage_factors calibrados por familia

| Familia | regular | round_of_16 | quarter | semi | final |
|---------|---------|-------------|---------|------|-------|
| Copa nacional (FA Cup, DFB-Pokal, etc.) | 0.90 | 1.00 | 1.10 | 1.20 | 1.40 |
| EFL Cup / copa menor | 0.80 | 0.90 | 1.00 | 1.10 | 1.30 |
| Europa League | 1.30 | 1.50 | 1.70 | 2.00 | 2.40 |
| Conference League | 1.10 | 1.25 | 1.40 | 1.60 | 2.00 |
| Supercopa 1 partido | — | — | — | — | 1.00–1.10 |
| Supercopas con semifinal | — | — | — | 1.10 | 1.30 |
| UEFA Super Cup | — | — | — | — | 2.00 |

FA Cup no tiene `round_of_16` en sus fixtures — no se inserta ese stage.

### D3 — competition_factor refleja el prestigio relativo

| Competición | competition_factor |
|------------|-------------------|
| Champions League (existente) | 1.50 |
| Europa League | 1.30 |
| Conference League | 1.10 |
| UEFA Super Cup | 1.05 |
| EFL Cup | 0.85 |
| Community Shield | 0.75 |
| DFL-Supercup | 0.85 |
| Supercoppa Italiana | 0.85 |
| Trophée des Champions | 0.80 |

### D4 — value_objects.py no se toca

`_DEFAULT_COMPETITION_BONUS_WEIGHTS` ya incluye los 8 nombres exactos. Cero cambios en dominio.

### D5 — API-Football league_ids para las 8 nuevas

| Competición | league_id | standings_league_id |
|-------------|-----------|---------------------|
| Europa League | 3 | 2 (CL) |
| Conference League | 848 | 2 (CL) |
| UEFA Super Cup | 531 | 2 (CL) |
| EFL Cup | 48 | 39 (PL) |
| Community Shield | 528 | 39 (PL) |
| DFL-Supercup | 529 | 78 (Bundesliga) |
| Supercoppa Italiana | 547 | 135 (Serie A) |
| Trophée des Champions | 526 | 61 (Ligue 1) |

### D6 — Re-ingestion de las 4 copas existentes

Las 4 copas ya ingresadas (FA Cup 45, DFB-Pokal 81, Coppa Italia 137, Coupe de France 66) tienen `player_events` con `m2=1.0` (fallback) porque en el momento de ingesta no había stages. Después de insertar los stages, hay que re-ingerir para que los eventos históricos tengan M2 correcto. Esto consume ~280 requests de API-Football — se hace manualmente cuando haya cuota disponible.

---

## Archivos afectados

1. `migrations/` — script SQL `0014_add_missing_competitions.sql`
2. `src/sfa/application/use_cases/ingest_competition.py` — 8 nuevas entradas en `LEAGUES`
