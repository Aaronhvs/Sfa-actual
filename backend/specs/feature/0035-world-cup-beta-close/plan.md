# Plan: 0035 — World Cup Beta Close

## Fases

- **Fase 1** — Quick wins seguros (banderas, Celery beat, click a partido Mundial)
- **Fase 2** — Backend API / data (explicabilidad, búsqueda por selección, sección países, perfil de selección)
- **Fase 3** — Scoring / recálculo [DDD] (passes_completed DEL/EXT, comparativa, nueva versión)
- **Fase 4** — UX avanzado (filtro posición+búsqueda combinados, overrides de posición, metodología)
- **Fase 5** — Auditoría y diagnóstico (alineaciones espejadas, temporadas de clubes locales)
- **Fase 6** — Producción rollout

---

## FASE 1 — Quick wins seguros

### 1A. Celery beat configurable (ítem 5)

**Archivo a modificar:** `src/sfa/celery_app.py`

- [ ] Leer `INGEST_INTERVAL_MINUTES` desde `settings` (añadir a `src/sfa/core/config.py`
  como `INGEST_INTERVAL_MINUTES: int = 30`).
- [ ] En `celery_app.py`, reemplazar `timedelta(minutes=30)` por
  `timedelta(minutes=settings.INGEST_INTERVAL_MINUTES)`.
- [ ] Añadir `INGEST_INTERVAL_MINUTES=10` al `.env` local y al VPS para el Mundial.
  El rollback post-Mundial es `INGEST_INTERVAL_MINUTES=30` + restart worker.
- [ ] Confirmar en logs que el beat schedule refleja el nuevo intervalo:
  `celery -A sfa.celery_app beat --loglevel=info` debe mostrar `every 10 minutes`.

**Criterio de completitud:** `GET /admin/health` o log de beat muestra intervalo = 10 min
en local con `INGEST_INTERVAL_MINUTES=10`.

### 1B. Banderas faltantes en mobile (ítem 6)

**Archivo a modificar:** `frontend/src/utils/worldCupTeams.ts`

- [ ] Añadir las 5 entradas faltantes en `WORLD_CUP_IDENTITIES`:
  ```typescript
  "ivory coast":         { name: "Costa de Marfil",     code: "CI" },
  "côte d'ivoire":       { name: "Costa de Marfil",     code: "CI" },
  curacao:               { name: "Curazao",              code: "CW" },
  "curaçao":             { name: "Curazao",              code: "CW" },
  "new zealand":         { name: "Nueva Zelanda",        code: "NZ" },
  "south africa":        { name: "Sudáfrica",            code: "ZA" },
  "bosnia & herzegovina": { name: "Bosnia y Herzegovina", code: "BA" },
  "bosnia and herzegovina": { name: "Bosnia y Herzegovina", code: "BA" },
  ```
- [ ] Verificar que `worldCupTeamFlagUrl("Ivory Coast")` retorna URL válida (no null).
- [ ] Verificar en `MatchTimeline`, ranking Mundial y `MundialPage` que las banderas
  aparecen en mobile (viewport 375px).

**Criterio de completitud:** `worldCupTeamFlagUrl("Ivory Coast")` !== null en consola del
navegador. Las 5 selecciones muestran bandera en mobile.

### 1C. Click desde partido del jugador hacia partido Mundial (ítem 3)

**Archivos a modificar:**
- `src/sfa/domain/ports.py` — `PlayerFixtureDTO`
- `src/sfa/infrastructure/repositories/sfa_score_repository.py` — query `get_player_fixtures`
- `src/sfa/api/v1/schemas/player_schemas.py` (o equivalente) — `PlayerFixtureSchema`
- `frontend/src/types/index.ts` — `PlayerFixture`
- `frontend/src/components/player/FixtureList.tsx` (o `FixtureRow.tsx`) — onClick

- [ ] Añadir `fixture_external_id: int | None = None` y `competition_id: int | None = None`
  al `PlayerFixtureDTO` (frozen dataclass, defaults None para backward-compat).
- [ ] En la query de `get_player_fixtures` en `sfa_score_repository.py`, hacer JOIN con
  `fixtures` para obtener `fixtures.external_id` y `fixtures.competition_id`. Mapear ambos al DTO.
- [ ] Añadir `fixture_external_id: int | None` y `competition_id: int | None` al schema
  Pydantic de respuesta (`PlayerFixtureResponseSchema` o equivalente).
- [ ] Añadir `fixture_external_id: number | null` y `competition_id: number | null` a la
  interfaz `PlayerFixture` en `frontend/src/types/index.ts`.
- [ ] En `FixtureRow.tsx` (o donde se renderiza cada partido del jugador), añadir onClick:
  ```typescript
  if (fixture.competition_id === 350 && fixture.fixture_external_id != null) {
    navigate(`/mundial/partido/${fixture.fixture_external_id}`)
  }
  ```
  Usar `useNavigate()` de React Router.
- [ ] El cursor debe cambiar a `pointer` en filas World Cup. Añadir clase CSS `.fx-row--wc-link`.
- [ ] Escribir test: `test_player_fixture_dto_includes_external_id` en
  `tests/use_cases/test_get_player_fixtures.py` (o crear si no existe).

**Criterio de completitud:** En perfil de jugador, click en un partido del Mundial navega a
`/mundial/partido/{fixture_external_id}` sin 404. Partidos de otros campeonatos no navegan.

---

## FASE 2 — Backend API / data

### 2A. Explicabilidad del detalle de partido por jugador (ítem 2)

Este ítem es mayoritariamente **frontend**: el backend ya devuelve `m1`, `m2`, `m3`, `m4`,
`mvisit` en `GET /players/{id}/events`. Lo que falta es UI.

- [ ] Verificar que `PlayerEvent` en `frontend/src/types/index.ts` ya tiene `m1`, `m2`,
  `m3`, `m4`, `mvisit`, `pts`. Confirmar con `GET /api/v1/players/{id}/events`.
- [ ] En el componente que muestra el detalle de evento (probable `ActionValues.tsx` o
  `ScoringExplainer.tsx`), añadir labels:
  - M1: si M1 > 1.05 → "Rival superior" (badge positivo); si M1 < 0.95 → "Rival menor"
    (badge neutro); si entre → "Rival similar"
  - Mvisit: si > 1.0 → "De visitante"
  - M3: si > 1.5 → "Alta presión" (derivado del minuto y marcador — el backend ya lo calcula)
  - M2: mostrar etiqueta de fase (ej. "Ronda 16", "Cuartos") si M2 != 1.0
- [ ] Añadir sección "Stats del partido" en `FixtureRow` o modal expandible:
  pases completados, precisión de pase, tiros al arco, tiros totales, pases clave,
  regates, duelos, tackles/intercepciones, bloqueos, faltas, tarjetas.
  Datos fuente: `PlayerFixture` ya tiene varios de estos campos (`shots_on`, `dribbles_won`,
  `duels_won`, `tackles_won`, `interceptions`, `blocks`, `fouls_drawn`).
- [ ] Verificar que NO se muestra "xG" ni "xA" como valor real — solo proxies con label
  explícito como "Remates sin gol" o "Pases clave sin asistencia".
- [ ] Añadir a `PlayerFixture` en types y al schema backend si faltan: `passes_completed`,
  `passes_total`, `passes_accuracy`, `fouls_committed`, `cards_yellow`, `cards_red`.
  Si el repository ya los tiene pero el schema los omite, solo es cambio de schema + types.

**Criterio de completitud:** En el perfil de un jugador con partidos del Mundial, expandir
un partido muestra M1 con label textual y al menos 8 stats de partido visibles. No aparece
el texto "xG" ni "xA" sin aclaración.

### 2B. Búsqueda ranking Mundial por selección/país (ítem 7)

**Archivo a modificar:** `src/sfa/infrastructure/repositories/sfa_score_repository.py`

- [ ] En el método `get_ranking`, extender el filtro `name`:
  ```python
  if name is not None:
      sub = stmt.subquery()
      final = (
          select(sub)
          .where(
              or_(
                  func.unaccent(sub.c.player_name).ilike(
                      func.concat("%", func.unaccent(name), "%")
                  ),
                  func.unaccent(sub.c.team_name).ilike(
                      func.concat("%", func.unaccent(name), "%")
                  ),
              )
          )
          .limit(limit)
      )
  ```
  Importar `or_` desde `sqlalchemy`.
- [ ] Aplicar el mismo cambio en `get_ranking_total` (para el count correcto).
- [ ] Aplicar en `get_ranking_all_seasons` y `get_ranking_total_all_seasons` también
  (para consistencia, aunque el uso principal es Mundial).
- [ ] Escribir test: `test_ranking_name_filter_matches_team_name` en
  `tests/use_cases/test_get_ranking.py`.

**Criterio de completitud:**
```bash
curl "http://localhost:8000/api/v1/ranking?season=2026&competition_id=350&name=Argentina"
# Debe retornar jugadores con team_name=Argentina, no solo nombre="Argentina"
```

### 2C. Endpoint de ranking SFA por selección (ítem 8 — backend)

**Archivos a crear:**
- `src/sfa/application/use_cases/get_wc_team_sfa_ranking.py`

**Archivos a modificar:**
- `src/sfa/domain/world_cup_ports.py` — añadir `WcTeamSFARankingDTO` y protocol
- `src/sfa/infrastructure/repositories/world_cup_repository.py` — implementar query
- `src/sfa/api/v1/schemas/wc_schemas.py` — añadir `WcTeamSFARankingSchema`
- `src/sfa/api/v1/wc_router.py` — añadir `GET /wc/teams/sfa-ranking`
- `src/sfa/core/dependencies.py` — wiring
- `http/world_cup.http` — caso HTTP

- [ ] Añadir `WcTeamSFARankingDTO(frozen dataclass)` en `domain/world_cup_ports.py`:
  campos `team_external_id`, `team_name`, `total_sfa_pts`, `total_goals`, `player_count`, `rank`.
- [ ] Añadir método `get_wc_team_sfa_ranking(season: str, rules_version_id: int | None) -> list[WcTeamSFARankingDTO]`
  al `WorldCupRepositoryProtocol`.
- [ ] Implementar en `WorldCupRepository`:
  ```sql
  SELECT t.external_id AS team_external_id,
         t.name AS team_name,
         SUM(ss.total_pts) AS total_sfa_pts,
         SUM(ps_agg.team_goals) AS total_goals,
         COUNT(DISTINCT ss.player_id) AS player_count
  FROM sfa_season_scores ss
  JOIN players p ON ss.player_id = p.id
  JOIN teams t ON ss.team_id = t.id
  -- subquery para goals por equipo por fixture (evitar duplicados)
  LEFT JOIN (
      SELECT ps.player_id, SUM(ps.goals) AS team_goals
      FROM player_stats ps
      JOIN fixtures f ON ps.fixture_id = f.id
      WHERE f.competition_id = 350 AND f.season = :season
      GROUP BY ps.player_id
  ) ps_agg ON ss.player_id = ps_agg.player_id
  WHERE ss.competition_id = 350
    AND ss.season = :season
    AND (ss.rules_version_id = :rv_id OR :rv_id IS NULL)
  GROUP BY t.external_id, t.name
  ORDER BY total_sfa_pts DESC
  ```
  Asignar `rank` con `row_number()` sobre `total_sfa_pts DESC`.
- [ ] Crear `GetWcTeamSFARankingUseCase` con `execute(season, rules_version_id)`.
- [ ] Añadir schema `WcTeamSFARankingSchema` y `WcTeamSFARankingResponseSchema`.
- [ ] Endpoint: `GET /api/v1/wc/teams/sfa-ranking?season=2026`.
- [ ] Wiring en `core/dependencies.py`.
- [ ] Tests: `tests/use_cases/test_get_wc_team_sfa_ranking.py` con Fake.

**Criterio de completitud:**
```bash
curl "http://localhost:8000/api/v1/wc/teams/sfa-ranking?season=2026"
# Retorna lista de selecciones ordenada por total_sfa_pts DESC con rank, total_goals, player_count
```

### 2D. Endpoint perfil de selección Mundial (ítem 9)

**Archivos a crear:**
- `src/sfa/application/use_cases/get_wc_team_profile.py`

**Archivos a modificar:**
- `src/sfa/domain/world_cup_ports.py` — añadir `WcTeamProfileDTO` y protocol method
- `src/sfa/infrastructure/repositories/world_cup_repository.py` — implementar
- `src/sfa/api/v1/schemas/wc_schemas.py` — `WcTeamProfileResponseSchema`
- `src/sfa/api/v1/wc_router.py` — `GET /wc/teams/{team_external_id}`
- `src/sfa/core/dependencies.py` — wiring
- `http/world_cup.http` — caso HTTP

- [ ] Añadir `WcTeamProfileDTO(frozen dataclass)` en `domain/world_cup_ports.py`:
  campos `team_external_id`, `team_name`, `total_sfa_pts`, `total_goals`, `fixtures: list[WorldCupFixtureDTO]`,
  `top_players: list[RankedPlayerDTO]` (top 5 por total_pts en WC).
- [ ] Añadir método `get_wc_team_profile(team_external_id: int, season: str, rules_version_id: int | None) -> WcTeamProfileDTO | None`
  al `WorldCupRepositoryProtocol`.
- [ ] Implementar en `WorldCupRepository` — combina:
  1. Query de partidos del equipo (ya disponible como subconjunto de `get_wc_fixtures`).
  2. Query de puntos SFA y goles (similar a 2C pero filtrado por equipo).
  3. Query top 5 jugadores (subquery sobre `sfa_season_scores` + `players`).
- [ ] `total_goals` debe provenir de `SUM(fixtures.home_goals)` donde el equipo es home
  + `SUM(fixtures.away_goals)` donde es away — fuente oficial del marcador. No de `player_stats`.
- [ ] Endpoint: `GET /api/v1/wc/teams/{team_external_id}`.
  Si `None` → 404.
- [ ] Schema `WcTeamProfileResponseSchema` con todos los campos del DTO + `top_players` como
  lista de `RankedPlayerSchema` (reutilizar el schema existente).
- [ ] Tests: `tests/use_cases/test_get_wc_team_profile.py` con Fake.

**Criterio de completitud:**
```bash
curl "http://localhost:8000/api/v1/wc/teams/26?season=2026"
# Retorna perfil de Argentina con total_sfa_pts, total_goals, top 5 jugadores, fixtures jugados
```

---

## FASE 3 — Scoring / recálculo [DDD]

### 3A. [DDD] Propuesta scoring DEL/EXT passes_completed (ítem 1)

**Acción previa obligatoria: comparativa local antes de producción.**

**Archivos a modificar:**
- `src/sfa/domain/scoring/services.py` — `BASE_POINTS_TABLE_V2`: DEL y EXT `PASSES_COMPLETED`
- Script de rollout: `scripts/create_b1_scoring_rules_version.py` (o nuevo `scripts/create_v23_scoring_rules.py`)

- [ ] **[DDD]** En `BASE_POINTS_TABLE_V2` (en `domain/scoring/services.py`):
  - `PositionGroup.DEL → ActionType.PASSES_COMPLETED: 2` (era 1)
  - `PositionGroup.EXT → ActionType.PASSES_COMPLETED: 3` (era 1)
  - `PositionGroup.MCO` se mantiene en 2. `PositionGroup.MF` se mantiene en 7.
  - `PositionGroup.LAT` y `PositionGroup.DC` se mantienen en 1.
- [ ] Crear script `scripts/create_v23_scoring_rules.py` que:
  1. Carga la config de `rules_version_id=4` (activa actual) vía `ScoringConfig.from_dict`.
  2. Sobreescribe `base_points[DEL][PASSES_COMPLETED] = 2` y `base_points[EXT][PASSES_COMPLETED] = 3`.
  3. Crea nueva versión `POST /api/v1/scoring-rules/versions` con nombre `"v2.3-del-ext-passes"`.
  4. Imprime el nuevo `rules_version_id`.
- [ ] **Comparativa local** (ejecutar antes del deploy):
  ```bash
  # 1. Recalcular con nueva versión solo para WC 2026:
  celery call calculate_scores_for_rules_version_task --args='[<nuevo_rv_id>, "2026", 350]'
  # 2. Comparar distribución de puntos DEL/EXT antes vs después:
  psql -U sfa -d sfa -c "
  SELECT p.position,
         ROUND(AVG(ss.total_pts)) as avg_v4,
         COUNT(*) as jugadores
  FROM sfa_season_scores ss
  JOIN players p ON ss.player_id = p.id
  WHERE ss.competition_id = 350 AND ss.season = '2026'
    AND ss.rules_version_id = 4
    AND p.position IN ('DEL','EXT')
  GROUP BY p.position;
  "
  # Repetir con el nuevo rules_version_id y comparar.
  ```
- [ ] Criterio de aceptación de la comparativa: el promedio de DEL/EXT sube entre 5-15%
  (no más, para no distorsionar el ranking frente a MF). Si el impacto es mayor, ajustar
  el valor antes de continuar.
- [ ] Si la comparativa es aceptable: activar la versión nueva como activa
  `POST /api/v1/scoring-rules/versions/{nuevo_rv_id}/activate`.
- [ ] Actualizar tests en `tests/use_cases/test_calculate_scores_for_rules_version.py`
  para reflejar los nuevos valores de DEL/EXT.

**Criterio de completitud:** Nueva `ScoringRulesVersion` activa con DEL=2 EXT=3 en
`passes_completed`. Query de comparativa documentada y ejecutada localmente con impacto dentro
del rango aceptable. Tests actualizados y `pytest` pasa.

---

## FASE 4 — UX avanzado

### 4A. Filtro por posición en ranking Mundial (ítem 15)

Este ítem es **frontend only**. El backend ya soporta `position` como query param.

- [ ] Verificar que `GET /ranking?season=2026&competition_id=350&position=EXT` funciona.
- [ ] En `frontend/src/pages/MundialPage.tsx` (o en el componente de ranking Mundial),
  añadir `FilterBar` con los mismos filtros de posición que en `RankingPage`:
  DEL, EXT, MCO, MF, LAT, DC.
- [ ] El filtro de posición debe funcionar en combinación con la búsqueda por nombre/selección.
  Pasar ambos params en la llamada a `fetchRanking`.
- [ ] Mantener el límite actual (50 o 100) y performance existente.

**Criterio de completitud:**
```bash
curl "http://localhost:8000/api/v1/ranking?season=2026&competition_id=350&position=DEL&name=Argentina"
# Retorna delanteros argentinos en el Mundial
```
En el frontend, seleccionar "DEL" filtra el ranking Mundial y combina con búsqueda de texto.

### 4B. Sección Países/Selecciones en MundialPage (ítem 8 — frontend)

**Depende de 2C** (`GET /wc/teams/sfa-ranking`).

- [ ] Añadir función `fetchWcTeamSFARanking(season: string)` en `frontend/src/api/client.ts`.
- [ ] Añadir interfaz `WcTeamSFARanking` en `frontend/src/types/index.ts`:
  `{ team_external_id, team_name, total_sfa_pts, total_goals, player_count, rank }`.
- [ ] En `MundialPage.tsx`, después del bloque de grupos/standings, añadir sección
  "Selecciones" (o "Países"):
  - Orden: por `total_sfa_pts DESC` (ya viene ordenado del endpoint).
  - Cards compactas: bandera + nombre en español + pts SFA + goles.
  - Click navega a `/mundial/seleccion/{team_external_id}`.
  - Usar `worldCupTeamName(team)` y `worldCupTeamFlagUrl(team.name)` para nombres y banderas.
- [ ] Añadir CSS `.wmd-countries__*` para la sección.
- [ ] Estado de carga y error (skeleton o mensaje).

**Criterio de completitud:** La sección "Selecciones" en `/mundial` muestra las selecciones
ordenadas por puntos SFA. Click en Argentina navega a `/mundial/seleccion/26`.

### 4C. Overrides de posición Mundial (ítem 11)

Solo si la comparativa 3A confirma que los overrides son necesarios para la beta.

- [ ] Auditar: `SELECT p.name, p.position FROM players p JOIN player_stats ps ON p.id = ps.player_id JOIN fixtures f ON ps.fixture_id = f.id WHERE f.competition_id = 350 ORDER BY p.name LIMIT 100;` — identificar jugadores con posición incorrecta en WC.
- [ ] Si se confirman casos críticos (ej. Messi como MC), crear diccionario en el use case
  de ranking (NO en DB):
  ```python
  # En get_ranking.py o en un módulo domain/wc_position_overrides.py
  WC_POSITION_OVERRIDES: dict[int, str] = {
      # player_external_id -> correct position for WC context
      # e.g. 154: "EXT",  # Messi
  }
  ```
  Aplicar el override solo cuando `competition_id == 350`.
- [ ] Este paso requiere auditoría manual de los casos. No implementar sin lista confirmada.

**Criterio de completitud:** Query de auditoría ejecutada. Lista de overrides confirmada y
aplicada en código. Messi aparece con posición correcta en ranking Mundial.

### 4D. Metodología B1 — documentar en frontend (ítem 14)

- [ ] Localizar la página de metodología en `frontend/src/pages/` (probable `MethodologyPage.tsx`
  o sección dentro de otra página).
- [ ] Añadir sección "B1 — Bonus de Edad Excepcional" con:
  - Descripción: aplica a goles y asistencias de jugadores jóvenes (17-20 años) o veteranos (35+).
  - Tabla de bonus: 1 contribución → +200 pts / 2 contribuciones → +400 pts / 3+ → +600 pts.
  - Aclaración: activo en beta del Mundial 2026. No aplica a goles en tanda de penales.
  - Ejemplo: jugador de 18 años con 1 gol recibe 200 pts adicionales sobre su total del partido.
- [ ] El bloque es contenido estático — no requiere endpoint nuevo.

**Criterio de completitud:** La página de metodología incluye la sección B1 con tabla de bonus
visible en desktop y mobile.

### 4E. Banderas en superficies de clubes (ítem 13)

Solo después de confirmar la regla exacta (no implementar sin decisión de diseño).

- [ ] Decisión de regla: la bandera en superficies de club corresponde al **país de la liga**
  (no del club ni del jugador), ya que un club puede tener jugadores de 30 países distintos.
  Excepción: si el club es una selección nacional (competition_id WC), usar la bandera del país.
- [ ] Verificar que la tabla `competitions` tiene campo `country` y que el país es consistente.
- [ ] Añadir `worldCupTeamFlagUrl`-equivalente para ligas: `leagueFlagUrl(country: string)`.
  Reutilizar `flagcdn.com` con el código ISO del país.
- [ ] Aplicar bandera en los lugares donde aparecen logos de clubs: `RankingRow`, `PlayerHeader`,
  `TeamCard` si existe.

**Criterio de completitud:** En el ranking global, cada fila de jugador muestra la bandera del
país de la liga (ej. bandera de España para jugadores de La Liga).

---

## FASE 5 — Auditoría y diagnóstico

### 5A. Alineaciones espejadas — auditoría (ítem 10)

No corregir código hasta completar el diagnóstico.

- [ ] Abrir `/mundial/partido/{fixture_colombia_uzbekistan}` en navegador.
- [ ] Inspeccionar los valores de `grid` en la API:
  ```bash
  curl "http://localhost:8000/api/v1/wc/fixtures/{fixture_id}" | jq '.lineups[0].start_xi[] | {name, grid}'
  ```
- [ ] Verificar si las coordenadas `grid` de Colombia (equipo "away") están siendo renderizadas
  con la orientación correcta o si el pitch CSS aplica `transform: scaleX(-1)` al equipo away.
- [ ] Comparar con el equipo home: ¿el espejo afecta a todos los equipos away o solo a Colombia?
- [ ] Revisar en `MundialMatchPage.tsx` el componente `CombinedTacticalPitch`:
  ¿existe algún `transform` o `flip` aplicado basado en `is_home`/`is_away`?
- [ ] Diagnóstico esperado en uno de estos tres:
  a) Las coordenadas API tienen `y` invertido para el equipo away → fix en el componente.
  b) El CSS aplica mirror innecesario → quitar transform.
  c) La asignación home/away en el backend es incorrecta → fix en el repository.
- [ ] Documentar el diagnóstico en un comentario en `MundialMatchPage.tsx` antes de aplicar fix.
- [ ] Aplicar fix quirúrgico según diagnóstico. No cambiar la orientación de todos los equipos.

**Criterio de completitud:** Colombia vs Uzbekistán muestra a Luis Díaz en el lado izquierdo
del campo (banda izquierda según su posición habitual). Auditado en al menos 2 partidos más
para confirmar que el fix no crea nuevos espejo.

### 5B. Corrector de posiciones Mundial — verificación (ítem 11, parte diagnóstico)

- [ ] Confirmar que `enrich-player-positions-daily` corre en el beat schedule con `season="2026"`.
  Verificar en logs del worker.
- [ ] Ejecutar query de auditoría (ver ítem 4C arriba) y listar casos problemáticos.
- [ ] Verificar si el corrector de Transfermarkt asigna `MC` a Messi porque Transfermarkt
  lo clasifica como `MF` en su posición registrada. Si es así, la solución es el override
  de 4C, no cambiar el corrector.

**Criterio de completitud:** Query de auditoría ejecutada y resultados documentados en
comentario o en el diccionario `WC_POSITION_OVERRIDES`.

### 5C. Temporadas de clubes no visibles en local — checklist de diagnóstico (ítem 12)

Árbol de diagnóstico (ejecutar en orden, detener cuando se encuentra la causa):

- [ ] **Check 1 — Datos en DB:**
  ```sql
  SELECT season, competition_id, COUNT(*) FROM sfa_season_scores GROUP BY season, competition_id ORDER BY season DESC LIMIT 20;
  ```
  ¿Hay filas para temporadas de clubes (ej. `season='2024'`)?

- [ ] **Check 2 — Rules version:**
  ```sql
  SELECT id, name, is_active FROM scoring_rules_versions ORDER BY id DESC LIMIT 5;
  SELECT DISTINCT rules_version_id FROM sfa_season_scores WHERE season = '2024' LIMIT 5;
  ```
  ¿El `rules_version_id` en los scores coincide con el activo?

- [ ] **Check 3 — API local:**
  ```bash
  curl "http://localhost:8000/api/v1/ranking?season=2024" | jq '.total'
  ```
  ¿Retorna jugadores? Si sí, es problema de frontend.

- [ ] **Check 4 — Frontend filter:**
  Revisar `RankingPage.tsx`: ¿existe algún filtro que excluye temporadas de clubes?
  ¿El selector de temporada en el dropdown incluye `2024`?

- [ ] **Check 5 — SeasonDropdown + endpoint seasons:**
  ```bash
  curl "http://localhost:8000/api/v1/seasons" | jq '.seasons'
  ```
  ¿Las temporadas de clubes están en la lista?

- [ ] Documentar causa raíz encontrada. Implementar fix solo si es trivial (< 10 líneas).
  Si requiere cambio estructural, abrir spec separado.

**Criterio de completitud:** Causa raíz identificada y documentada. Si es fix trivial, aplicado.

---

## FASE 6 — Producción rollout

### 6A. Preparación VPS

- [ ] **Backup DB:**
  ```bash
  pg_dump -U sfa -d sfa -Fc -f /backup/sfa_pre_0035_$(date +%Y%m%d).dump
  ```
- [ ] Confirmar rama/commit: `git log --oneline -5`.
- [ ] Pull y build:
  ```bash
  git pull origin main
  docker compose -f docker-compose-production.yml build api worker
  ```

### 6B. Migración (solo si aplica)

Este spec no añade nuevas tablas. Las tablas de specs 0033 y 0034 deben estar ya aplicadas.
Verificar:
```sql
SELECT table_name FROM information_schema.tables WHERE table_name IN ('fixture_events');
SELECT column_name FROM information_schema.columns WHERE table_name = 'players' AND column_name = 'birth_date';
```
Si no existen:
```bash
psql -U sfa -d sfa -f migrations/0033_create_fixture_events.sql
psql -U sfa -d sfa -f migrations/0034_add_birth_date_to_players.sql
```

### 6C. Deploy y restart

- [ ] Reiniciar API y worker:
  ```bash
  docker compose -f docker-compose-production.yml up -d api worker beat
  ```
- [ ] Configurar `INGEST_INTERVAL_MINUTES=10` en `.env.production` antes de restart beat.

### 6D. Enrichment y recálculo (post-deploy)

- [ ] Si `birth_date` no está enriquecido:
  ```bash
  curl -X POST "https://api.sfa.com/api/v1/admin/enrich-birth-dates?season=2026" -H "X-Admin-Key: $ADMIN_KEY"
  ```
- [ ] Crear nueva versión v2.3 (si 3A fue aceptada localmente):
  ```bash
  python scripts/create_v23_scoring_rules.py
  ```
- [ ] Recalcular Mundial con nueva versión:
  ```bash
  curl -X POST "https://api.sfa.com/api/v1/admin/recalculate/350?season=2026" -H "X-Admin-Key: $ADMIN_KEY"
  ```
- [ ] Activar nueva versión como activa si recálculo es satisfactorio.
- [ ] Backfill de eventos de cronología para partidos ya jugados (si no se hizo antes):
  ```bash
  # Para cada fixture_external_id del Mundial:
  curl -X POST "https://api.sfa.com/api/v1/admin/fixtures/{fixture_id}/ingest-events" -H "X-Admin-Key: $ADMIN_KEY"
  ```

### 6E. Smoke tests VPS

```bash
# 1. Fixtures Mundial
curl "https://api.sfa.com/api/v1/wc/fixtures" | jq '.fixtures | length'

# 2. Detalle partido con events
curl "https://api.sfa.com/api/v1/wc/fixtures/1539016" | jq '{events: (.events | length), lineups: (.lineups | length)}'

# 3. Ranking Mundial con filtro posición
curl "https://api.sfa.com/api/v1/ranking?season=2026&competition_id=350&position=EXT" | jq '.total'

# 4. Búsqueda por selección
curl "https://api.sfa.com/api/v1/ranking?season=2026&competition_id=350&name=Argentina" | jq '.ranking[0].team'
# Esperado: "Argentina"

# 5. Ranking SFA selecciones
curl "https://api.sfa.com/api/v1/wc/teams/sfa-ranking?season=2026" | jq '.rankings[0]'

# 6. Perfil selección
curl "https://api.sfa.com/api/v1/wc/teams/26?season=2026" | jq '{team: .team_name, pts: .total_sfa_pts, goals: .total_goals}'

# 7. Celery beat interval
docker compose -f docker-compose-production.yml exec beat celery inspect scheduled | grep "ingest-today"
```

### 6F. Rollback

- **Rollback scoring:** activar versión anterior `POST /api/v1/scoring-rules/versions/4/activate`
  + recalcular con `rules_version_id=4`.
- **Rollback Celery beat:** cambiar `INGEST_INTERVAL_MINUTES=30` en `.env.production` + restart beat.
- **Rollback endpoints nuevos:** si el deploy rompe algún endpoint existente, hacer rollback del
  contenedor con la imagen anterior: `docker compose rollback api`.
- **Rollback DB:** si hay problema en migración (no aplica aquí ya que este spec no migra):
  ```bash
  pg_restore -U sfa -d sfa --clean /backup/sfa_pre_0035_YYYYMMDD.dump
  ```

---

## Archivos a crear (resumen)

- [ ] `src/sfa/application/use_cases/get_wc_team_sfa_ranking.py`
- [ ] `src/sfa/application/use_cases/get_wc_team_profile.py`
- [ ] `scripts/create_v23_scoring_rules.py`
- [ ] `tests/use_cases/test_get_wc_team_sfa_ranking.py`
- [ ] `tests/use_cases/test_get_wc_team_profile.py`
- [ ] `tests/use_cases/test_get_player_fixtures_wc_link.py` (o extender test existente)
- [ ] `http/world_cup_teams.http`

## Archivos a modificar (resumen)

- [ ] `src/sfa/celery_app.py` — `INGEST_INTERVAL_MINUTES` env var
- [ ] `src/sfa/core/config.py` — añadir `INGEST_INTERVAL_MINUTES: int = 30`
- [ ] `src/sfa/domain/ports.py` — `PlayerFixtureDTO`: `fixture_external_id`, `competition_id`
- [ ] `src/sfa/domain/world_cup_ports.py` — `WcTeamSFARankingDTO`, `WcTeamProfileDTO`, nuevos protocol methods
- [ ] `src/sfa/infrastructure/repositories/sfa_score_repository.py` — `name` filter extiende a team_name
- [ ] `src/sfa/infrastructure/repositories/world_cup_repository.py` — implementar nuevos protocol methods
- [ ] `src/sfa/api/v1/schemas/wc_schemas.py` — `WcTeamSFARankingSchema`, `WcTeamProfileResponseSchema`
- [ ] `src/sfa/api/v1/wc_router.py` — `GET /wc/teams/sfa-ranking`, `GET /wc/teams/{team_external_id}`
- [ ] `src/sfa/core/dependencies.py` — wiring de los 2 nuevos use cases
- [ ] `src/sfa/domain/scoring/services.py` — `BASE_POINTS_TABLE_V2` DEL y EXT `PASSES_COMPLETED` [DDD]
- [ ] `frontend/src/utils/worldCupTeams.ts` — 5 entradas faltantes en `WORLD_CUP_IDENTITIES`
- [ ] `frontend/src/types/index.ts` — `PlayerFixture` (ext_id, competition_id), `WcTeamSFARanking`
- [ ] `frontend/src/api/client.ts` — `fetchWcTeamSFARanking`
- [ ] `frontend/src/pages/MundialPage.tsx` — sección Selecciones + filtro posición en ranking
- [ ] `frontend/src/components/player/FixtureRow.tsx` (o similar) — click WC + labels explicabilidad

---

## Verificación final local

```bash
# Backend
docker compose -f docker-compose-development.yml exec -T api pytest tests/use_cases -q
docker compose -f docker-compose-development.yml exec -T api flake8 src/ tests/
docker compose -f docker-compose-development.yml exec -T api isort --check-only src/ tests/

# Frontend
cd frontend && npm run build
```

---

## Agent Routing Brief

**DDD Designer needed:** yes

**Ítem 3A** — La modificación de `BASE_POINTS_TABLE_V2` en `domain/scoring/services.py`
(cambiar `PASSES_COMPLETED` para `DEL` de 1→2 y para `EXT` de 1→3) toca el subdomain de
scoring. El DDD Designer debe:

1. Verificar que el cambio en `BASE_POINTS_TABLE_V2` no rompe invariantes existentes
   en `ScoringConfig` ni en `SFAScoringService`.
2. Confirmar que la propagación correcta es:
   - Cambio en `services.py` (tabla literal para `default_v2()`)
   - Serializar los nuevos valores en la nueva versión via `ScoringConfig.to_dict()`
   - No requiere cambio en `value_objects.py` ya que los valores base son lookup-table,
     no value objects calculados.
3. Verificar que los tests de `test_calculate_scores_for_rules_version.py` que mockean
   base points para DEL/EXT sean actualizados con los nuevos valores de referencia.

El resto de los ítems de este spec (endpoints, DTO, frontend, Celery, banderas) no requieren
modelado DDD — son extensiones de la capa de aplicación e infraestructura con el patrón
hexagonal estándar ya establecido en el proyecto.
