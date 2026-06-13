# Compare Extended — Comparador enriquecido head-to-head

## Contexto de negocio

El endpoint `GET /compare` actual devuelve únicamente `PlayerDetailResult` (sfa_pts total,
goles, asistencias, breakdown de temporada) para dos jugadores. La UI necesita 7 bloques de
comparación que requieren datos de tres fuentes adicionales: events, fixtures y season stats.

Los campos solicitados van desde simples agregados (goles por tipo, tarjetas) hasta
métricas derivadas propias de SFA (impacto crítico con M3 ≥ 1.6, actuaciones élite,
racha anotadora) que no tienen equivalente en APIs externas y cuya lógica no debe
exponerse al cliente.

El endpoint actual `/compare` es consumido por el frontend existente con `CompareResponse`.
Cualquier cambio en ese contrato rompe la UI en producción.

## Restricciones

- `rating` nunca puede aparecer en ningún campo de respuesta — regla de seguridad absoluta.
- El frontend actual usa `/compare` — no puede romperse.
- La lógica de "racha anotadora", "momentos críticos" y "actuaciones élite" debe calcularse
  server-side: la lógica de M3, score_diff y sfa_pts threshold no debe filtrarse al cliente.
- `PlayerSeasonStatsDTO.get_player_season_stats` requiere `competition_id` — para el
  comparador se agrega sobre todas las competiciones disponibles del jugador en la temporada
  (estrategia multi-competition descrita en Decisiones).
- La racha anotadora requiere ordenar fixtures por `played_at` — los fixtures ya vienen
  ordenados `DESC` desde el repositorio; hay que revertir antes de calcular la racha.
- Los goles de jugada por 90 min requieren `minutos_totales`, que proviene de los fixtures
  (suma de `minutes` por fixture), no de season stats (que dependen de competition_id).
- El cálculo de `home_sfa_pts_avg` y `away_sfa_pts_avg` requiere saber si el jugador
  jugó como local o visitante. En `PlayerFixtureDTO` no hay un campo `player_team`
  explícito — se infiere desde `SFAScoreRepository.get_best_score_for_player_season`
  que ya tiene `team_name`. El use case recibe `PlayerDetailResult` que incluye `team`.

## Decisiones arquitectónicas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nuevo endpoint `GET /compare/extended` | Enriquecer `/compare` existente | El frontend actual consume `/compare`; cambiar el response model rompe la UI. Un endpoint nuevo es aditivo y no destructivo. |
| Nuevo use case `CompareExtendedUseCase` | Ampliar `ComparePlayersUseCase` | SRP: el use case existente solo orquesta `GetPlayerDetailUseCase`. El nuevo orquesta 4 repos; mezclarlos viola el principio de responsabilidad única. |
| Cálculos derivados server-side en el use case | Enviar raw events/fixtures al frontend | M3, score_diff, breakdown keys son lógica de dominio SFA que no debe conocer el cliente. El servidor es más eficiente (menos payload, menos cómputo JS). |
| Agregar season stats sobre todas las competiciones | Requerir `competition_id` como query param | El comparador es cross-competition por naturaleza (jugador A en Liga vs jugador B en Premier). Forzar competition_id rompe el caso de uso principal. |
| Obtener team del jugador desde `PlayerDetailResult.team` | Query adicional a `PlayerRepository` | `GetPlayerDetailUseCase` ya resuelve el team; reutilizarlo evita una query extra. La inferencia local/visitante se hace comparando `team` con `home_team` en cada fixture. |
| Calcular `passes_key_per_game` desde season stats agregado | Desde eventos individuales | `passes_key` es una stat de match (PlayerStats), no un evento puntual; su agregado ya existe en `PlayerSeasonStatsDTO`. |
| `corner_assists` separado en bloque asistencias | Sumarlo todo en `total_assists` | `PlayerDetailResult.total_assists` ya incluye corner_assists. Separarlo en el comparador permite a la UI diferenciar creatividad de asistencias "normales". |
| Método nuevo `get_all_season_stats_for_player` en `PlayerEventRepositoryProtocol` | Múltiples llamadas a `get_player_season_stats` por competition | Evita N queries (una por competición); el repo puede hacer un GROUP BY sin filtrar `competition_id`. |

## Estrategia multi-competition para season stats

`get_player_season_stats` actual requiere `competition_id`. Para el comparador necesitamos
aggregates globales de temporada. Se añade un nuevo método al Protocol:

```
PlayerEventRepositoryProtocol.get_all_season_stats_for_player(player_id, season)
    -> PlayerSeasonStatsDTO | None
```

Este método agrega `player_stats` filtrando solo por `player_id` y temporada (via JOIN con
`fixtures.season`), sin filtrar por `competition_id`. El DTO retornado es el mismo
`PlayerSeasonStatsDTO` con `competition_id = 0` como sentinel (indica "todas").

## Domain Model — CompareExtendedResult

```
CompareExtendedResult (frozen dataclass)
├── season: str
├── player_a: PlayerExtendedStats
└── player_b: PlayerExtendedStats

PlayerExtendedStats (frozen dataclass)
├── # Identidad (de PlayerDetailResult)
│   id: int
│   name: str
│   team: str
│   position: str
│   competition: str
│   photo_url: str | None
│   global_rank: int
│   competitions: list[str]
│
├── # Bloque 1 — Resumen visual
│   sfa_pts: float
│   matches: int
│
├── # Bloque 2 — Goles desglose
│   goals_open_play: int          # events goal
│   goals_penalty: int            # events goal_penalty
│   goals_shootout: int           # events goal_shootout
│   goals_total: int              # suma de los tres
│   penalty_goal_pct: float | None   # goals_penalty / goals_total * 100, None si goals_total=0
│   goals_open_play_per90: float | None  # goals_open_play / total_minutes * 90, None si minutes=0
│   minutes_per_goal: float | None   # total_minutes / goals_total, None si goals_total=0
│   total_minutes: int            # suma minutes de todos los fixtures
│
├── # Bloque 3 — Asistencias
│   assists_total: int            # assist + corner_assist (de PlayerDetailResult)
│   corner_assists: int           # solo corner_assist del breakdown de season
│   minutes_per_assist: float | None    # total_minutes / assists_total, None si assists_total=0
│   minutes_per_goal_contribution: float | None  # total_minutes / (goals_total + assists_total)
│
├── # Bloque 4 — Impacto crítico
│   critical_goals_assists: int   # events (goal/assist) con m3 >= 1.6
│   avg_m3_on_goals: float | None  # promedio m3 de events tipo goal* (no shootout ni penalty)
│   avg_m1_on_goals: float | None  # promedio m1 de events tipo goal*
│   elite_performances: int       # fixtures con sfa_pts >= 2500
│   decisive_goals: int           # goals con score_diff in {-1, 0} en el momento del gol
│
├── # Bloque 5 — Eficiencia
│   avg_sfa_pts_per_match: float | None  # sfa_pts / matches
│   home_sfa_pts_avg: float | None      # media sfa_pts en fixtures donde player juega local
│   away_sfa_pts_avg: float | None      # media sfa_pts en fixtures donde player juega visitante
│   max_scoring_streak: int             # partidos consecutivos con gol o asistencia
│
├── # Bloque 6 — Métricas por posición
│   dribble_success_rate: float | None  # de season stats
│   shots_on_per_game: float | None     # shots_on / matches
│   passes_key_per_game: float | None   # passes_key / matches
│   xa_no_assist_pts: float | None      # del season breakdown: xa_no_assist.pts
│   duel_win_rate: float | None         # de season stats
│   tackles_interceptions_per_game: float | None  # (tackles_won + interceptions) / matches
│
└── # Bloque 7 — Disciplina
    cards_yellow: int
    cards_red: int
    fouls_committed_per_game: float | None   # fouls_committed / matches
    pts_lost_discipline: float | None        # yellow_card.pts + red_card.pts + fouls_committed.pts (negativo)
```

## Fuentes de datos por campo

| Campo | Fuente | Método repo |
|---|---|---|
| `goals_open_play`, `goals_penalty`, `goals_shootout` | `PlayerEventDTO.event_type` | `get_events_by_player` |
| `total_minutes` | `sum(f.minutes for f in fixtures)` | `get_fixtures_by_player` |
| `corner_assists` | `PlayerDetailResult.breakdown["corner_assist"].count` | ya en PlayerDetailResult |
| `critical_goals_assists` | `PlayerEventDTO.m3 >= 1.6`, event_type in goal/assist family | `get_events_by_player` |
| `avg_m3_on_goals`, `avg_m1_on_goals` | `PlayerEventDTO.m3`, `m1` donde event_type=goal | `get_events_by_player` |
| `decisive_goals` | `PlayerEventDTO.score_diff in {-1, 0}`, event_type=goal* | `get_events_by_player` |
| `elite_performances` | `PlayerFixtureDTO.sfa_pts >= 2500` | `get_fixtures_by_player` |
| `home_sfa_pts_avg` / `away_sfa_pts_avg` | `PlayerFixtureDTO.home_team == player.team` | `get_fixtures_by_player` |
| `max_scoring_streak` | ordenar fixtures por `played_at ASC`, detectar rachas | `get_fixtures_by_player` + events para marcar fixture con gol/asistencia |
| `dribble_success_rate`, `duel_win_rate`, `passes_key`, `fouls_committed`, `cards_*` | `PlayerSeasonStatsDTO` | `get_all_season_stats_for_player` (nuevo método) |
| `xa_no_assist_pts` | `PlayerDetailResult.breakdown["xa_no_assist"].pts` | ya en PlayerDetailResult |
| `pts_lost_discipline` | `PlayerDetailResult.breakdown["yellow_card"].pts + ["red_card"].pts + ["fouls_committed"].pts` | ya en PlayerDetailResult |

## Cálculo de racha anotadora (max_scoring_streak)

1. Obtener todos los `fixture_id` donde el jugador tiene evento `goal*` o `assist*` (de events).
2. Obtener lista de fixtures ordenados por `played_at ASC`.
3. Para cada fixture: marcar `scored = fixture_id in scored_fixture_ids`.
4. Recorrer la lista y calcular la racha máxima de `True` consecutivos.

Este cálculo es O(N) sobre la lista de fixtures, completamente en memoria en el use case.

## Inferencia local/visitante

En `PlayerFixtureDTO`:
- Si `home_team == player_detail.team` → partido local
- Si `away_team == player_detail.team` → partido visitante
- Casos edge (team renombrado, etc.): ignorar ese fixture en la media (no afecta a la mayoría)

## Seguridad — campos prohibidos

`rating` (`PlayerFixtureDTO.rating`, `PlayerSeasonStatsDTO.rating_avg`) nunca se incluye
en ningún campo del response ni en ningún cálculo intermedio expuesto. Los campos
`avg_m3_on_goals` y `avg_m1_on_goals` usan únicamente los multiplicadores M3 y M1 del
evento, que son propios de SFA y no tienen relación con el rating de API-Football.

## Impacto en capas existentes

| Capa | Cambio |
|---|---|
| `domain/ports.py` | Añadir `get_all_season_stats_for_player` al Protocol `PlayerEventRepositoryProtocol` |
| `infrastructure/repositories/player_event_repository.py` | Implementar `get_all_season_stats_for_player` |
| `application/use_cases/` | Nuevo archivo `compare_extended.py` |
| `api/v1/schemas/compare.py` | Añadir schemas del nuevo response (sin tocar `CompareResponseSchema`) |
| `api/v1/compare.py` | Añadir handler `GET /compare/extended` al router existente |
| `core/dependencies.py` | Nueva factory `get_compare_extended_use_case` |
| `main.py` | Sin cambios (el router ya está registrado) |
| `tests/use_cases/` | Nuevo archivo `test_compare_extended.py` |
| `http/` | Nuevo archivo `compare_extended.http` |
