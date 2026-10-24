# 0067 — "Lidera en": estadísticas en las que el jugador es top 3

Fecha: 2026-10-21. Diseño Architecture-Engineer con modelado de dominio aplicado según `backend/.claude/agents/DDD-Designer.md`; skill `backend/.claude/skills/sfa-spec/SKILL.md` aplicada. Solo diseño: no autoriza despliegue, migraciones ni cambios de puntuación.

## Contexto de negocio

El perfil de jugador muestra muchas cifras, pero un aficionado casual no ve de un vistazo qué hace especial al jugador. "Lidera en" enseña como máximo tres estadísticas en las que el jugador es #1 (o, como mucho, top 3) frente a jugadores comparables del mismo periodo. Ejemplo motivador: Raphinha con 14 goles en 19 tiros a puerta, posiblemente la mejor eficacia de la temporada.

Como SFA aún no es conocido, el catálogo prioriza estadísticas que cualquier aficionado entiende y conserva **una única** métrica propia de SFA ("Mejor contra los grandes"), que refuerza la identidad del algoritmo sin exigir conocer los SFA pts. Si el jugador no lidera nada, la API devuelve una lista vacía y el frontend oculta la sección.

El valor diferencial depende de que los liderazgos sean **creíbles**: un jugador con 1 gol en 1 tiro no puede "liderar" con un 100 %. Por eso este spec fija fórmulas, mínimos y grupos de comparación exactos.

## Restricciones

- Fuente de estadísticas: `player_stats` (una fila por jugador y fixture, origen API-Football `fixtures/players`). Verificado en código: `tackles_won` contiene en realidad `tackles.total` del proveedor (mapeo `tackles_won: ps.tackles` en `ingest_competition.py`, `backfill_fixture_stats.py`, `reingest_player.py`), por lo que la métrica defensiva se comunica como **entradas**, no "entradas ganadas". `dribbles_won` contiene `dribbles.success`.
- `player_stats` no guarda penaltis lanzados, fallados ni parados. Sí existen eventos `player_events.event_type = goal_penalty` para penaltis anotados en juego (las tandas usan `goal_shootout*`/`missed_shootout*`, no cuentan). Los penaltis fallados/parados en juego no se ingieren como eventos (filtro `is_missed_penalty_event` en ingesta), así que solo pueden excluirse los penaltis **marcados**.
- `goals_conceded` y `saves` vienen del bloque `goals` del proveedor; `goals_conceded` es "goles encajados mientras estaba en el campo" e incluye penaltis y autogoles. No existe "tiros a puerta recibidos": se aproxima como `saves + goals_conceded`.
- Nivel del rival: el motor ya guarda la fuerza previa al partido por equipo y fixture en `fixture_team_strengths.pre_match_strength` (0-100, `EloCalculatorService.normalize` = (ELO-1400)/700·100 con clamp), que es la entrada de M1 en `PlayerEventScoreRepository`. Es la misma escala que `frontend/src/utils/teams.ts` (bandas Élite ≥70, Alto ≥50, Medio ≥30, Bajo).
- Puntos SFA por acción: `player_event_scores.final_points` por `rules_version_id`. No tiene `team_id`; el equipo del jugador en el fixture se toma de `player_stats.team_id` (snapshot inmutable de aparición).
- Scopes: `AwardPeriodScope` resuelto por `SeasonRepository.resolve_scope` (`season-YYYY` como award period, que puede incluir el Mundial físico como fuente adicional; `world-cup-YYYY` como torneo). El perfil usa `season=all` para el histórico.
- Posiciones: el contrato desplegado del ranking usa `Player.position` + overrides de `position_for_context` (`domain/player_position_overrides.py`) con el equipo verificado más reciente del contexto. Las posiciones por evidencia de 0065 no están desplegadas; este spec no puede depender de ellas.
- Working tree compartido con cambios de posiciones sin commitear (0065) y otros. La implementación debe limitarse a los archivos de este spec y no arrastrar cambios ajenos.
- Redis ya está disponible (`infrastructure/redis_client.py`, usado por `FixtureDetailRepository` con TTL). No hay cache servidor para el ranking (0060 lo descartó para esa vista).
- Cobertura: mismo criterio que 0066: ≥80 % de líneas en módulos nuevos y en líneas modificadas; suite completa sin fallos.

## Decisiones de producto (2026-10-21, respuesta del responsable)

1. Eficacia: se ordena **sin penaltis** pero la respuesta incluye también la cifra bruta (`goals`, `shots_on` y `penalty_goals_excluded` en `details`) para que el frontend muestre "14 de 19 a puerta (2 de penal)".
2. "Mejor contra los grandes": por 90', mostrando también el total (`big_points` en `details`).
3. Rival grande = Alto o Élite (`pre_match_strength ≥ 50`).
4. El grupo de scope completo **no mezcla selecciones con clubes**: en award periods solo suma competiciones `participant_kind = club` (el Mundial sigue formando su propio grupo de competición).
5. Mínimos de grupo (10/6) y corte de 450' aceptados; se afinan con datos reales.
6. **Se elimina `goals_conceded_per90`** (depende de la defensa, no del portero). El catálogo `leads-v1` queda en 9 métricas, todas en orden descendente.
7. Histórico ("all") fuera de v1.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Endpoint `GET /api/v1/players/{player_id}/leads?scope=&max_rank=3&limit=3` en el router `players.py` existente | Incrustar los leads en `GET /players/{id}` | Cálculo y cache distintos; no ralentiza ni rompe el detalle. El perfil lo pide en paralelo y oculta la sección si viene vacía. |
| Solo `scope` (award period o torneo); sin `scope` → scope latest; `scope=all` → 200 con `supported=false` e `items=[]` | Soportar histórico ("all") en v1 | Un liderazgo multi-temporada mezcla versiones de reglas, eras y plantillas; la narrativa "lidera esta temporada" es la del producto. El frontend ya distingue `season=all`. |
| Eficacia de cara a puerta = goles sin penalti / tiros a puerta sin penalti, ordenada por **límite inferior de Wilson al 95 %** (z = 1,96) y mostrando la cifra bruta | Ordenar por porcentaje bruto con un mínimo; media bayesiana con prior de liga; tiros por gol con tiros totales | Wilson premia el volumen de forma estándar y explicable: 14/19 → 0,51; 6/7 → 0,49; 3/3 → 0,44; 1/1 → 0,21. No necesita un prior por liga que habría que calibrar. Un mínimo solo sigue dejando ganar a 5/5. "Tiros por gol" con tiros totales mide casi lo mismo, es menos intuitivo y duplicaría liderazgos; se descarta como métrica (los tiros totales se devuelven como detalle). |
| Excluir penaltis marcados del numerador y del denominador de la eficacia | Usar goles y tiros a puerta brutos | Un penalti es un tiro a puerta casi gratis (~75-80 % de acierto) que infla la eficacia de los lanzadores. Los datos permiten restar los `goal_penalty`; los penaltis parados no se pueden restar y quedan en el denominador (sesgo conservador documentado). |
| `goals_per90` y `goal_contributions_per90` usan goles **con** penaltis | Goles sin penalti también aquí | Es la cifra que el aficionado reconoce ("goles por partido"); el volumen por minuto no se distorsiona como un porcentaje. |
| Todas las métricas de tasa (eficacia, duelos, paradas) se ordenan por Wilson LB; las de volumen por 90' se ordenan por valor por 90 con mínimo de minutos y de eventos | Mezclar criterios por métrica | Un solo método para proporciones, testeable en dominio y fácil de explicar ("ajustado por volumen"). |
| Mínimo de minutos relativo al avance: `max(F, ceil(0,30 · M_max))`, con F = 270 (award period) o 180 (torneo) y `M_max` = máximo de minutos de cualquier jugador en el grupo | Mínimo fijo (p. ej. 900') | Igual filosofía que 0066 (umbral que escala con el periodo): funciona en la jornada 5 y a final de temporada (liga completa: ~1.026'). |
| Mínimos de intentos también relativos: `max(piso, ceil(0,25 · máximo del grupo))` (pisos por métrica en el catálogo) | Solo mínimo de minutos | Las tasas necesitan volumen propio; un central con muchos minutos y 3 duelos no debe liderar porcentajes. |
| Grupos: (a) competición, todas las posiciones elegibles; (b) competición × posición; (c) scope completo (todas las fuentes del award period), todas las posiciones y por posición | Solo competición | (a)/(b) son los liderazgos más legibles; (c) da "mejor de la temporada en Europa" con la misma suma que ya muestra `/players/{id}/stats?scope=`, así las cifras cuadran con el panel del perfil. (c) solo existe en award periods con ≥2 competiciones; en torneos solo hay (a)/(b). |
| Competiciones demasiado cortas no forman grupo: `M_max` de la competición ≥ 450' (award period) o ≥ 270' (torneo) | Permitir Supercopas y Community Shield | Liderar una competición de 1-2 partidos no es un logro creíble. |
| Tamaño mínimo de grupo calificado: 10 en grupos de todas las posiciones, 6 en grupos por posición | Sin mínimo | Ser #1 de 3 calificados no es noticia; MCO (pocos jugadores por overrides) cae así de forma natural. |
| Empates con ranking de competición estándar (1, 1, 3) sobre el valor de orden redondeado a 6 decimales; `tied=true` si comparte puesto | Desempatar por ID | Un empate real se comunica como empate; el orden interno estable (desempates por métrica, minutos, `player_id`) solo decide el orden de listas. |
| Una entrada por métrica (se conserva el mejor grupo) y máximo `limit` entradas (por defecto 3, máximo 5) | Mostrar la misma métrica en varios grupos | "#1 en goles/90 en LaLiga" y "#1 entre extremos de LaLiga" dicen lo mismo; se elige el grupo más impresionante. |
| Orden de "excepcionalidad": rank asc → prioridad de grupo (scope todas > competición todas > scope posición > competición posición) → percentil desc (`1 - (rank-1)/calificados`) → calificados desc → orden del catálogo | Score continuo compuesto | Determinista, explicable y testeable; ser #1 de una competición entera pesa más que serlo en una posición. |
| Métrica SFA "Mejor contra los grandes" = SFA pts por 90' en fixtures contra rivales con `pre_match_strength ≥ 50` (Alto o Élite) | Total de puntos acumulados; usar M1 del evento | El total depende del calendario (número de partidos grandes) y favorece a quien juega más Champions; por 90' con mínimo mide rendimiento real. M1 es un multiplicador combinado, no una banda; la fuerza pre-partido es la misma entrada y la misma escala que el frontend. |
| Puntos de la métrica SFA = Σ `player_event_scores.final_points` de la versión de reglas resuelta para el scope (`resolve_rules_version_id_for_scope`); sin bonos de logros ni honores | Usar `sfa_season_scores` | Solo los eventos tienen fixture y por tanto rival; bonos y honores no se ganan "contra" nadie. |
| Si la versión de reglas del scope es inconsistente: se calculan las métricas estadísticas y se omite la SFA (`rules_version_id=null`) | 409 como `/players/{id}` | Las estadísticas no dependen de reglas; degradar es mejor que ocultar toda la sección. |
| Cálculo de **todos** los liderazgos del scope de una vez + cache Redis por scope, consultado por jugador con `HGET` | (1) Calcular solo los rangos del jugador por request con window functions; (2) tabla/materialized view rellenada por Celery tras el scoring; (3) sin cache | (1) el rango exige agregar el grupo completo igualmente (~150k filas `player_stats` por temporada) en cada visita de perfil; (2) requiere migración y engancharse a varios puntos de entrada del scoring (ingesta live, recálculo, full recalculation), con riesgo de quedar obsoleta; (3) coste repetido en la página más visitada. El snapshot completo por scope es pequeño (grupos × métricas × top 3 ≈ miles de entradas) y se reutiliza para todos los perfiles. |
| Clave de cache `player-leads:{policy_version}:{scope_key}:{rules_version_id|none}:{stamp}`; `stamp` = huella de `max(last_updated)` y `count(*)` de `sfa_season_scores` del scope y versión, más `max(fixtures.id)` final del scope; TTL 12 h | Invalidación explícita desde tareas Celery | El scoring siempre reescribe `sfa_season_scores` tras ingerir; la huella cambia sola sin acoplar tareas. El TTL acota cualquier caso no cubierto. `policy_version` (`leads-v1`) invalida al cambiar fórmulas/mínimos. |
| Anti-estampida con `SET NX` de 120 s; quien no obtiene el lock calcula y responde sin escribir. Redis caído → cálculo directo con warning | Esperar con polling | Solo ocurre al invalidar; simple y sin bloqueo. La feature no debe tumbar el perfil si Redis falla. |
| La API devuelve claves y números; los textos en español los compone el frontend | Devolver frases | Consistente con `breakdown` y honores; el copy se itera sin desplegar backend. |
| Posición de comparación = posición de contexto del ranking desplegado: `Player.position` + `position_for_context` con el equipo verificado más reciente del grupo | Posiciones por evidencia de 0065 | 0065 no está desplegado. El repository encapsula la resolución para cambiarla cuando 0065 se publique, sin tocar dominio ni API. |
| Población base: fixtures finales (`FT`, `AET`, `PEN`), filas con `minutes > 0` y `player_stats.team_id` igual a local o visitante del fixture | Incluir partidos en vivo | Igual que scoring y `_verified_player_ids`; un liderazgo no debe oscilar durante un partido. |
| Sin migración en v1 | Añadir índices preventivos | Validar con `EXPLAIN ANALYZE` en clon; solo si el cálculo en frío supera el presupuesto se añade un índice concreto (ítem condicional del plan). |

## Catálogo de métricas (`leads-v1`)

Notación por jugador y grupo: sumas sobre las filas de `player_stats` de la población base. Valores "por 90" = cuenta × 90 / minutos. Todas las métricas exigen además el mínimo de minutos del grupo salvo indicación.

1. **`shot_conversion` — Eficacia de cara a puerta.** Posiciones: todas menos GK. Por fixture: `pen = least(goles_penalti_eventos, goals)`, `np_goals = goals - pen`, `np_shots_on = greatest(shots_on - pen, np_goals)` (el `greatest` corrige filas en las que el proveedor da más goles que tiros a puerta; se registra en log el número de filas corregidas). Orden: Wilson LB de `np_goals / np_shots_on`, desc; desempate `np_goals` desc, minutos asc, `player_id` asc. Mínimos: `np_shots_on ≥ max(8, ceil(0,25 · máx. del grupo))` y `np_goals ≥ 3`. Muestra: `value` = porcentaje bruto, numerador `np_goals`, denominador `np_shots_on`; detalles: `penalty_goals_excluded`, `shots_total`.
2. **`goals_per90` — Goles por 90'.** Todas menos GK. Orden por 90 desc; mínimo `goals ≥ 3`. Numerador goles (con penaltis), denominador minutos.
3. **`goal_contributions_per90` — Goles + asistencias por 90'.** Todas menos GK. Mínimo `goals + assists ≥ 4`. Detalles: `goals`, `assists`.
4. **`key_passes_per90` — Pases clave por 90'.** Todas menos GK. Mínimo `passes_key ≥ 10`.
5. **`dribbles_per90` — Regates completados por 90'.** Todas menos GK. Orden: `dribbles_won` por 90 desc. Mínimo `dribbles_attempts ≥ max(15, ceil(0,25 · máx. del grupo))`. Detalles: `dribbles_attempts`, `success_rate` (bruto).
6. **`defensive_actions_per90` — Entradas + intercepciones por 90'.** Solo DC, LAT, MC. Numerador `tackles_won + interceptions`. Detalles: `tackles`, `interceptions`.
7. **`duel_win_rate` — Duelos ganados (%).** Solo DC, LAT, MC. Wilson LB de `duels_won / duels_total`. Mínimo `duels_total ≥ max(40, ceil(0,25 · máx. del grupo))`.
8. **`save_rate` — Paradas (%).** Solo GK. `k = saves`, `n = saves + goals_conceded`. Wilson LB. Mínimo `n ≥ max(15, ceil(0,25 · máx. del grupo))`. Se documenta como aproximación (incluye penaltis y autogoles).
9. ~~`goals_conceded_per90`~~ — eliminada por decisión de producto (punto 6).
10. **`big_game_points_per90` — Mejor contra los grandes (métrica SFA).** Todas menos GK. Fixture "grande": la fuerza `pre_match_strength` del rival (el equipo del fixture distinto de `player_stats.team_id`) ≥ 50. `big_points` = Σ `final_points` de la versión resuelta en esos fixtures; `big_minutes`/`big_matches` = minutos y fixtures con minutos > 0 en esos fixtures. Orden: `big_points × 90 / big_minutes` desc. Mínimos: `big_minutes ≥ max(F, ceil(0,30 · máx. big_minutes del grupo))` (F = 270 award / 180 torneo) y `big_matches ≥ 3` (award) o `≥ 2` (torneo). No aplica el mínimo general de minutos. Fixtures sin snapshot de fuerza del rival se excluyen. Detalles: `big_points` total, `big_matches`, `elite_matches` (rival ≥ 70).

Grupos para métricas con restricción de posición: el grupo "todas" es la población restringida (p. ej. "entre defensas y centrocampistas"); los subgrupos por posición solo se generan si la restricción tiene más de una posición (no para GK).

## Domain Model

Nuevo subdominio de lectura `domain/player_leads/`, separado de `domain/scoring/` porque no afecta al cálculo de SFA pts: consume estadísticas y puntos ya calculados.

### Nuevas entidades

Ninguna. Los liderazgos no tienen identidad ni ciclo de vida: son proyecciones derivadas y recalculables. Todo se modela como value objects inmutables y un servicio de dominio puro.

### Value objects nuevos

- **`LeadMetric`** (enum str): las 9 claves del catálogo; el orden de declaración es el orden de catálogo usado como último desempate.
- **`LeadGroupKind`** (enum str): `competition`, `competition_position`, `scope`, `scope_position`, con prioridad fija para el orden de excepcionalidad.
- **`RateCount`**: `successes`, `attempts` enteros con invariante `0 ≤ successes ≤ attempts`; `attempts = 0` es válido pero no produce tasa. Expone tasa bruta y Wilson LB con z = 1,96 (resultado en [0, 1]). Construcción con valores negativos o `successes > attempts` lanza `ValueError` (el repository ya corrige por fixture; el VO protege el invariante).
- **`LeadSample`**: muestra por jugador y fuente (`player_id`, `season`, `competition_id`, nombre y `participant_kind` de la competición, posición de contexto ya resuelta o `None`) con contadores no negativos: `minutes`, `matches`, `goals`, `assists`, `np_goals`, `np_shots_on`, `penalty_goals`, `shots_total`, `passes_key`, `dribbles_won`, `dribbles_attempts`, `duels_won`, `duels_total`, `tackles`, `interceptions`, `saves`, `goals_conceded`, `big_points` (decimal, puede ser negativo), `big_minutes`, `big_matches`, `elite_matches`. Invariantes: contadores ≥ 0 (salvo `big_points`), `np_goals ≤ np_shots_on`, `dribbles_won ≤ dribbles_attempts`, `duels_won ≤ duels_total`, `big_minutes ≤ minutes`. Es sumable para construir la muestra de scope (la posición de scope llega aparte).
- **`LeadPolicy`**: constantes de `leads-v1` (pisos F por tipo de scope, fracciones 0,30/0,25, pisos por métrica, mínimos de competición 450/270, tamaños de grupo 10/6, banda grande 50 y élite 70, `max_rank` permitido 1-3, `limit` 1-5, `policy_version`). Funciones puras para el mínimo de minutos y de intentos dado el máximo del grupo.
- **`MetricDefinition`**: clave, posiciones elegibles (o todas menos GK), dirección (desc/asc), método (`per90` o `wilson_lower_bound`), extractores de numerador/denominador y regla de mínimos. Catálogo inmutable en el dominio.
- **`LeadThreshold`**: mínimos aplicados en el grupo (`min_minutes`, `min_attempts` y su `attempts_kind`, `min_events`) para devolverlos en la API.
- **`LeadGroup`**: `kind`, `season`/`competition_id`/`competition_name` (nulos en grupos de scope), `position` (nulo si no es por posición).
- **`PlayerLead`**: `metric`, `group`, `rank` (≥1), `tied`, `qualified_count` (≥ tamaño mínimo), `value` (cifra de muestra), `ranking_value` (valor de orden), `method`, `numerator`, `denominator`, `threshold`, `details` (mapa clave→número). Invariante: `rank ≤ qualified_count`.
- **`PlayerLeadsSnapshot`**: resultado de un scope: `policy_version`, `scope_key`, `rules_version_id` opcional, mapa `player_id → tuple[PlayerLead]` ya deduplicado por métrica y ordenado por excepcionalidad (todas las entradas con rank ≤ 3).

### Servicio de dominio

- **`PlayerLeadsCalculator`** (puro, sin I/O): recibe muestras por competición, contexto de posición de scope por jugador, tipo de scope y si la métrica SFA está disponible. Construye grupos (aplica mínimos de competición), calcula mínimos por grupo sobre todos los jugadores del grupo antes de filtrar, filtra calificados, aplica tamaño mínimo de grupo, ordena con desempates estables, asigna ranks con empates, conserva rank ≤ 3, deduplica por métrica y ordena por excepcionalidad. Devuelve `PlayerLeadsSnapshot`.

### Ubicación propuesta en domain/

- `src/sfa/domain/player_leads/__init__.py`
- `src/sfa/domain/player_leads/models.py` — enums y value objects
- `src/sfa/domain/player_leads/policy.py` — `LeadPolicy`, `MetricDefinition` y catálogo `leads-v1`
- `src/sfa/domain/player_leads/calculator.py` — `PlayerLeadsCalculator`
- `src/sfa/domain/player_leads/ports.py` — `PlayerLeadsRepositoryProtocol` (muestras por competición, contexto de posición de scope, huella de datos) y `PlayerLeadsCacheProtocol` (leer entradas de un jugador, saber si existe snapshot, guardar snapshot, lock)

Coherencia con el modelo existente: usa `Position` de `domain/enums.py` (incluido MCO) y `position_for_context` para overrides; no añade `ActionType`, multiplicadores ni toca `BASE_POINTS_TABLE`.

## Contrato API

`GET /api/v1/players/{player_id}/leads`

Query: `scope` opcional (clave de award period o torneo; ausente = latest; `all` = no soportado), `max_rank` (1-3, por defecto 3), `limit` (1-5, por defecto 3).

Respuesta 200: `player_id`, `scope` (clave resuelta o `null`), `scope_label`, `supported` (bool), `policy_version`, `rules_version_id` (o `null`), `items` (lista). Cada item: `metric`, `rank`, `tied`, `qualified_count`, `percentile`, `group` {`kind`, `season`, `competition_id`, `competition_name`, `position`}, `value`, `ranking_value`, `method`, `numerator`, `denominator`, `minimums` {`minutes`, `attempts`, `attempts_kind`, `events`}, `details` (objeto clave→número). Jugador inexistente o sin muestra: 200 con `items=[]` (sin consulta extra). Scope desconocido: 404 (igual que `/players/{id}`). Valores fuera de rango en `max_rank`/`limit`: 422.

Ejemplo narrativo esperado (no contractual): Raphinha, `shot_conversion`, rank 1 de 38 en LaLiga, `numerator` 14, `denominator` 19 (si ninguno de sus goles fue de penalti), `value` 0,737, `ranking_value` 0,512, mínimos 8 tiros a puerta y 1.026'.

## Integraciones externas

Ninguna nueva. Solo lectura de PostgreSQL (`player_stats`, `player_events`, `fixtures`, `competitions`, `players`, `teams`, `fixture_team_strengths`, `player_event_scores`, `sfa_season_scores`) y Redis existente. Sin llamadas a API-Football: no consume cuota.

## Fuera de alcance

- Histórico multi-temporada ("all").
- Precalentado del cache desde Celery tras el scoring (posible mejora si el cálculo en frío se acerca al presupuesto).
- Diseño visual de la sección del perfil: lo resuelve el frontend con su propio flujo (`frontend/PRODUCT.md`, `frontend/DESIGN.md`, skill `impeccable`); este spec solo fija el contrato y la integración de datos.
- Cambiar ingesta para guardar penaltis fallados/parados.


## Published position correction (2026-10-24, leads-v2)

The deployed ranking uses `scope_position` over `scope_reference_position`, with the existing
legacy expression only as a fallback. Leads now reuses that exact projection in its two
position-resolution methods. Calling only `sfa_current_position` would miss the published
scope classifications (including C. Casseres). No scoring, domain grouping, use-case or API
contract changes are required.

Competition groups resolve the position using that competition and the ranking's latest
verified team context. Season groups use the latest verified club team and highest-scoring
club competition under the resolved rules version, matching the unfiltered scope ranking.
Latest scopes evaluate habitual roles at `now()`; historical scopes evaluate them at the
maximum fixture date across all scope sources, exactly as the shared ranking helper does.
The appearance/statistics population remains finished fixtures with positive minutes.

`LeadPolicy.policy_version` is `leads-v2`, so Redis cannot reuse a v1 snapshot. Only obsolete
`player-leads:leads-v1:*` keys may be removed after deployment; no Redis database is flushed.

Main was missing the already deployed position projection and its ORM dependency. The
committed dependency snapshot comes from deployed commit `f4874e8`, including migrations
0052/0053 and 0054 (the latter defines scope classifications). These migrations are already
applied in production and must not be rerun there. The PostgreSQL regression fixture installs
them only in the explicitly isolated `leads_test` database when their schema markers are absent.
No uncommitted position redesign or ingestion changes are included.
