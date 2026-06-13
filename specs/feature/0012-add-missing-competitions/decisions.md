# ADR 0012 — Add Missing Competitions + Fix Cup Stages

**Status:** Accepted
**Date:** 2026-06-01
**Author:** Architecture Engineer (SFA)

---

## Contexto de negocio

El sistema actualmente cubre 12 competiciones. El roadmap objetivo incluye 20 competiciones
(5 ligas, 7 copas nacionales, 5 torneos europeos/supercopas). Existen dos problemas
diferenciados que este spec resuelve juntos porque comparten la misma migración SQL:

1. **Stages faltantes en 4 copas existentes:** FA Cup, DFB-Pokal, Coppa Italia y Coupe de
   France tienen fixtures en DB pero cero filas en `competition_stages`. Como resultado,
   `get_stage_factor()` devuelve el fallback `1.0` para *todos* sus partidos — cuartos,
   semis y finales son subvalorados porque el multiplicador M2 no refleja la eliminatoria.

2. **8 competiciones ausentes:** Europa League, Conference League, UEFA Super Cup, EFL Cup,
   Community Shield, DFL-Supercup, Supercoppa Italiana y Trophée des Champions no tienen
   entrada en `competitions` ni en `LEAGUES`, por lo que nunca se ingieren.

Resolverlo ahora es condición necesaria para completar el universo de competiciones antes
del cierre de la temporada 2024-25 y para que los perfiles reflejen participación en
competiciones europeas secundarias.

---

## Restricciones

- `competition_factor` es `NUMERIC(4,2)` con `CHECK (competition_factor > 0)`. Máximo
  almacenable: 99.99. Rango real usado: 0.80 – 1.50.
- `competition_stages.stage_factor` es `NUMERIC(4,2)` con `CHECK (stage_factor > 0)`.
- `competition_stages` tiene `UNIQUE (competition_id, stage)` — el INSERT debe usar
  `ON CONFLICT DO NOTHING` o `ON CONFLICT DO UPDATE` para ser idempotente.
- `LEAGUES` en `ingest_competition.py` es una lista plana de `LeagueConfig`. El orden
  determina la prioridad cuando `IngestAllCompetitionsUseCase` alcanza el límite de
  7 000 peticiones (de 7 500 diarias disponibles).
- La corrección del M2 histórico para las 4 copas existentes **requiere re-ingestión
  completa**, no solo recálculo. El valor `player_events.m2` se escribe en ingest time;
  `calculate_competition_scores_task` sólo re-agrega eventos ya almacenados sin
  recomputar multiplicadores.
- UEFA Super Cup (league_id=531) no tiene standings propios; el proveedor devolverá lista
  vacía. `IngestCompetitionUseCase` ya retorna `IngestionResult` temprano en ese caso.
  Se asigna `standings_league_id=2` (Champions League) como contexto de fortaleza de
  equipo.
- API-Football quota: 7 500 req/día. Añadir 8 competiciones incrementa el consumo en
  temporadas completas. El guard de 7 000 en `IngestAllCompetitionsUseCase` sigue vigente.

---

## Decisiones tomadas

| # | Decisión elegida | Alternativa descartada | Razón |
|---|---|---|---|
| 1 | Insertar stages para FA Cup sin `round_of_16` | Agregar `round_of_16` igualmente | Los fixtures existentes en DB no usan ese stage; insertar un stage sin fixtures es inofensivo pero genera ruido en auditorías |
| 2 | stage_factor escala 1.00–1.50 para copas nacionales | Escala 0.90–1.40 igual que Copa del Rey | Copa del Rey tiene `comp_factor=1.0` y empieza en 0.90 para penalizar rounds tempranos; el resto de copas también tienen `comp_factor=1.0` — la escala 1.00–1.50 es equivalente (el producto `comp_factor × stage_factor` da el mismo rango efectivo) |
| 3 | Europa League y Conference League copian stages de Champions League | Stages propios diferenciados | Mismo formato UEFA, misma lógica de ronda. No hay razón de negocio para valorar distinto un gol en cuartos de UEL vs CL en términos de M2 — la diferencia de prestigio ya la captura `comp_factor` |
| 4 | UEFA Super Cup: stage único `final(2.00)` | `final(1.50)` igual que copas nacionales | Es una final europea entre campeones de CL y EL — prestige comparable a una semifinal de CL (2.30) pero inferior; 2.00 es un punto medio razonado |
| 5 | Single-match competitions (Community Shield, DFL-Supercup, Trophée des Champions): `final(1.10–1.20)` | `final(1.50)` | Son supercopas de pretemporada de menor trascendencia; escala reducida coherente con sus `comp_factor` 0.80–0.90 |
| 6 | No cambiar `value_objects.py` | Añadir nuevas entradas a `_DEFAULT_COMPETITION_BONUS_WEIGHTS` | El dict ya contiene las 8 competiciones nuevas con los pesos correctos. Sin cambios necesarios |
| 7 | Re-ingestión para corregir M2 histórico de 4 copas existentes | Solo ejecutar `calculate_all_scores_task` | `calculate_competition_scores_task` re-agrega `player_events` existentes pero no reescribe `m2`. Para que las finales/semis históricas tengan M2>1.0 es necesario re-ingerir |
| 8 | Migration numerada `0014` | Número arbitrario | Última migración existente es `0013_scoring_v2_impact_model.sql` |
| 9 | `LeagueConfig.top_n=None` para todas las nuevas competiciones | Limitar top_n en copas de un solo partido | `top_n=None` significa "todos los equipos de standings". Para copas de partido único los standings prestados (ej. Premier League con 20 equipos) iterarán los 20 equipos pero sólo se procesarán los 2 que tengan fixtures en esa competición — idempotente y correcto |

---

## Integraciones externas

**API-Football v3** — Únicos league_ids relevantes:

| Competición | league_id | Tipo de standings |
|---|---|---|
| Europa League | 3 | Group stage standings propios |
| Conference League | 848 | Group stage standings propios |
| UEFA Super Cup | 531 | Sin standings (partido único) → borrow league_id=2 |
| EFL Cup | 48 | Sin standings → borrow league_id=39 (Premier League) |
| Community Shield | 528 | Sin standings → borrow league_id=39 |
| DFL-Supercup | 529 | Sin standings → borrow league_id=78 (Bundesliga) |
| Supercoppa Italiana | 547 | Sin standings → borrow league_id=135 (Serie A) |
| Trophée des Champions | 526 | Sin standings → borrow league_id=61 (Ligue 1) |

Los league_ids han sido verificados contra la documentación oficial de API-Football v3
(`/leagues` endpoint, parámetros `id` y `type`).

---

## Competition factors y stage factors — tabla completa

### Competiciones existentes sin stages (a corregir)

| Competición | `competition_factor` (ya en DB) | Stages a insertar |
|---|---|---|
| FA Cup | 1.00 | regular=1.00, quarter=1.20, semi=1.30, final=1.50 |
| DFB-Pokal | 1.00 | regular=1.00, round_of_16=1.10, quarter=1.20, semi=1.30, final=1.50 |
| Coppa Italia | 1.00 | regular=1.00, round_of_16=1.10, quarter=1.20, semi=1.30, final=1.50 |
| Coupe de France | 1.00 | regular=1.00, round_of_16=1.10, quarter=1.20, semi=1.30, final=1.50 |

### Nuevas competiciones a insertar

| Competición | country | `competition_factor` | Stages |
|---|---|---|---|
| Europa League | EUR | 1.20 | group=1.50, regular=1.50, round_of_16=1.80, quarter=2.00, semi=2.30, final=2.80 |
| Conference League | EUR | 1.00 | group=1.50, regular=1.50, round_of_16=1.80, quarter=2.00, semi=2.30, final=2.80 |
| UEFA Super Cup | EUR | 1.10 | final=2.00 |
| EFL Cup | ENG | 0.90 | regular=1.00, quarter=1.20, semi=1.30, final=1.50 |
| Community Shield | ENG | 0.80 | final=1.20 |
| DFL-Supercup | GER | 0.90 | final=1.20 |
| Supercoppa Italiana | ITA | 0.90 | semi=1.10, final=1.30 |
| Trophée des Champions | FRA | 0.85 | final=1.10 |

---

## Capas tocadas

| Capa | Archivo | Tipo de cambio |
|---|---|---|
| Migración SQL | `backend/migrations/0014_add_missing_competitions.sql` | Nuevo archivo |
| Application — config | `backend/src/sfa/application/use_cases/ingest_competition.py` | Añadir 8 entradas a `LEAGUES` |
| Domain scoring | `backend/src/sfa/domain/scoring/value_objects.py` | Sin cambio |
| Celery tasks | `backend/src/sfa/tasks/ingestion_tasks.py` | Sin cambio |
| Infra models | `backend/src/sfa/infrastructure/models/competitions/models.py` | Sin cambio |
