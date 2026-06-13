# Plan 0012 — Add Missing Competitions

## Checklist

- [ ] **1. SQL — competition_stages para copas existentes sin stages**
  - Insertar stages para FA Cup (90): regular, quarter, semi, final
  - Insertar stages para DFB-Pokal (92): regular, round_of_16, quarter, semi, final
  - Insertar stages para Coppa Italia (94): regular, round_of_16, quarter, semi, final
  - Insertar stages para Coupe de France (96): regular, round_of_16, quarter, semi, final
  - Criterio: `SELECT COUNT(*) FROM competition_stages WHERE competition_id IN (90,92,94,96)` → 19 rows

- [ ] **2. SQL — 8 nuevas competiciones en `competitions`**
  - Insertar Europa League, Conference League, UEFA Super Cup, EFL Cup, Community Shield, DFL-Supercup, Supercoppa Italiana, Trophée des Champions
  - Criterio: `SELECT COUNT(*) FROM competitions` → 20 rows

- [ ] **3. SQL — competition_stages para las 8 nuevas**
  - Insertar stages según D2 de decisions.md
  - Criterio: `SELECT COUNT(*) FROM competition_stages WHERE competition_id IN (SELECT id FROM competitions WHERE name IN ('Europa League','Conference League','UEFA Super Cup','EFL Cup','Community Shield','DFL-Supercup','Supercoppa Italiana','Trophée des Champions'))` > 0

- [ ] **4. Código — `LEAGUES` en `ingest_competition.py`**
  - Agregar 8 nuevas entradas `LeagueConfig` con los league_ids de D5
  - Criterio: `len(LEAGUES) == 20`

- [ ] **5. Re-cálculo v2 para las 4 copas existentes** (requiere stages del paso 1)
  - Lanzar `calculate_scores_for_rules_version_task` con `rules_version_id=3, season=2024, force_recalculate=True`
  - Criterio: `SELECT COUNT(*) FROM sfa_season_scores WHERE rules_version_id=3` aumenta (nuevas competiciones apareceran)

- [ ] **6. Re-ingestion de las 4 copas existentes** (cuando haya cuota API disponible)
  - FA Cup (45), DFB-Pokal (81), Coppa Italia (137), Coupe de France (66)
  - Corregirá M2 histórico en `player_events`
  - Criterio: logs sin `m2=1.0` fallback en eventos de copa

## Agent Routing Brief

No hay ítems `[DDD]`. Todo este spec es datos de referencia + configuración + un cambio menor en `LEAGUES`. No requiere invocar `@DDD-Designer`.
