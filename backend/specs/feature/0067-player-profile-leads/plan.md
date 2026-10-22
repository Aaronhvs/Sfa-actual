# Plan: "Lidera en" — estadísticas en las que el jugador es top 3

Referencia obligatoria: `decisions.md` de este spec (catálogo `leads-v1`, fórmulas, mínimos, grupos, cache y contrato). Si algo de este plan contradice `decisions.md`, prevalece `decisions.md`.

## Archivos a crear

- [ ] `src/sfa/domain/player_leads/__init__.py` — exporta el API público del subdominio
- [ ] `src/sfa/domain/player_leads/models.py` — `LeadMetric`, `LeadGroupKind`, `RateCount`, `LeadSample`, `LeadThreshold`, `LeadGroup`, `PlayerLead`, `PlayerLeadsSnapshot` (frozen, con invariantes)
- [ ] `src/sfa/domain/player_leads/policy.py` — `LeadPolicy` (`leads-v1`), `MetricDefinition` y catálogo de las 9 métricas
- [ ] `src/sfa/domain/player_leads/calculator.py` — `PlayerLeadsCalculator` puro
- [ ] `src/sfa/domain/player_leads/ports.py` — `PlayerLeadsRepositoryProtocol`, `PlayerLeadsCacheProtocol` y DTO de contexto de posición de scope
- [ ] `src/sfa/application/use_cases/get_player_leads.py` — `GetPlayerLeadsUseCaseProtocol`, `GetPlayerLeadsUseCase`, `GetPlayerLeadsResult`
- [ ] `src/sfa/infrastructure/repositories/player_leads_repository.py` — consultas SQLAlchemy de muestras, contexto de posición y huella de datos
- [ ] `src/sfa/infrastructure/repositories/player_leads_cache.py` — adaptador Redis (hash por scope, TTL 12 h, lock `SET NX`)
- [ ] `tests/domain/test_player_leads_models.py` — invariantes de VOs y Wilson
- [ ] `tests/domain/test_player_leads_policy.py` — mínimos relativos y catálogo
- [ ] `tests/domain/test_player_leads_calculator.py` — grupos, mínimos, empates, deduplicación y orden
- [ ] `tests/use_cases/test_get_player_leads.py` — flujo con Fakes (scope, versión, cache, degradación)
- [ ] `tests/repositories/test_player_leads_repository_postgres.py` — integración contra PostgreSQL aislado (patrón `test_ranking_eligibility_postgres.py`, skip sin variable de entorno)
- [ ] `tests/repositories/test_player_leads_cache.py` — adaptador Redis con Fake/cliente en memoria
- [ ] `tests/test_player_leads_api.py` — contrato HTTP con dependency override

## Archivos a modificar

- [ ] `src/sfa/api/v1/schemas/players.py` — añadir `PlayerLeadGroupSchema`, `PlayerLeadMinimumsSchema`, `PlayerLeadSchema`, `PlayerLeadsResponseSchema`
- [ ] `src/sfa/api/v1/players.py` — nuevo endpoint `GET /players/{player_id}/leads` (el router ya está registrado en `main.py`)
- [ ] `src/sfa/core/dependencies.py` — factories del repository, cache y use case
- [ ] `http/players.http` — peticiones de ejemplo del endpoint
- [ ] `frontend/src/types/index.ts` — tipos `PlayerLead`/`PlayerLeadsResponse` (fase frontend, ver checklist)
- [ ] `frontend/src/api/client.ts` — `fetchPlayerLeads(id, scope)` con cache de módulo (fase frontend)

## Checklist de implementación

### 0. Preparación

- [ ] Confirmar que 0067 es el siguiente número libre en `specs/feature/` y `specs/refactor/` en el momento de implementar; si no, renombrar la carpeta sin cambiar el contenido.
- [ ] Ejecutar la suite completa antes de tocar código y registrar el baseline (passed/skipped/errores) en el PR. Criterio: número anotado.
- [ ] Trabajar solo sobre los archivos listados; no incluir cambios de posiciones (0065) ni otros cambios del working tree en el commit. Criterio: `git diff --stat` del commit solo contiene archivos de este plan.

### 1. Dominio [DDD]

- [ ] [DDD] Crear `LeadMetric` con las 9 claves exactas de `decisions.md` en el orden de catálogo. Criterio: test que compara la lista de valores.
- [ ] [DDD] Crear `LeadGroupKind` con prioridad `scope` < `competition` < `scope_position` < `competition_position` (menor = más excepcional). Criterio: test de orden.
- [ ] [DDD] Crear `RateCount` con invariante `0 ≤ successes ≤ attempts`, tasa bruta (None si `attempts = 0`) y Wilson LB con z = 1,96. Criterio: tests 14/19 → 0,512 (±0,001), 6/7 → 0,487 (±0,001), 3/3 → 0,439 (±0,001), 1/1 → 0,207 (±0,001), 0/10 → 0, 10/10 < 1, y `ValueError` para negativos y `successes > attempts`.
- [ ] [DDD] Crear `LeadSample` con los contadores de `decisions.md`, invariantes (no negativos salvo `big_points`, `np_goals ≤ np_shots_on`, `dribbles_won ≤ dribbles_attempts`, `duels_won ≤ duels_total`, `big_minutes ≤ minutes`) y suma de muestras del mismo jugador. Criterio: tests de cada invariante y de la suma.
- [ ] [DDD] Crear `LeadThreshold`, `LeadGroup`, `PlayerLead` (invariante `1 ≤ rank ≤ qualified_count`; `percentile` = `1 - (rank-1)/qualified_count`) y `PlayerLeadsSnapshot`. Criterio: tests de invariantes y percentil.
- [ ] [DDD] Crear `LeadPolicy` (`policy_version = "leads-v1"`) con: F minutos 270/180, fracción minutos 0,30, fracción intentos 0,25, mínimo de competición 450/270, tamaño de grupo 10/6, banda grande 50, élite 70, `max_rank` 1-3, `limit` 1-5 (por defecto 3/3). Funciones `min_minutes(m_max, scope_kind)` y `min_attempts(max_group, floor)`. Criterio: tests m_max 0 → 270, 3420 → 1026, 600 → 270, torneo 450 → 180, intentos máx. 60 piso 8 → 15, máx. 10 piso 8 → 8.
- [ ] [DDD] Crear `MetricDefinition` y el catálogo de las 9 métricas con posiciones elegibles, dirección, método, numerador/denominador, mínimos de eventos/intentos y detalles exactamente como en `decisions.md`. Criterio: test por métrica que verifica posiciones, dirección, método y pisos.
- [ ] [DDD] Implementar `PlayerLeadsCalculator`: construcción de grupos (competición, competición × posición, scope y scope × posición; scope solo en award period con ≥2 competiciones de clubes y sumando solo clubes; subgrupos de posición solo para restricciones de más de una posición; competiciones descartadas por `M_max` bajo). Criterio: tests de grupos generados para award period de 1 y 3 competiciones y para torneo.
- [ ] [DDD] Calcular `M_max`, máximo de intentos y máximo de `big_minutes` sobre **toda** la población elegible del grupo antes de filtrar calificados. Criterio: test donde el líder de minutos no califica por otra métrica y aun así fija el umbral.
- [ ] [DDD] Aplicar mínimos por métrica y el tamaño mínimo de grupo (10/6). Criterio: tests de jugador 1/1 excluido de `shot_conversion`, grupo de 9 calificados sin entradas, grupo de posición con 6 sí.
- [ ] [DDD] Ordenar con desempates de `decisions.md`, asignar rank de competición estándar sobre el valor redondeado a 6 decimales y marcar `tied`. Criterio: test con dos jugadores empatados en #1 y el siguiente en #3.
- [ ] [DDD] Excluir `big_game_points_per90` si la métrica SFA no está disponible y aplicar sus mínimos propios (`big_minutes`, `big_matches` 3/2) sin el mínimo general de minutos. Criterio: tests de disponibilidad y mínimos.
- [ ] [DDD] Deduplicar por métrica (mejor grupo según el orden de excepcionalidad) y ordenar entradas: rank asc → prioridad de grupo → percentil desc → calificados desc → orden de catálogo. Criterio: test con el mismo jugador #1 en competición y #1 en posición que devuelve solo la de competición; test de orden entre tres métricas.
- [ ] [DDD] Caso de referencia: muestra sintética con un jugador 14 goles sin penalti / 19 tiros a puerta y otro 5/5 dentro de un grupo de ≥10 calificados; el primero es #1 de `shot_conversion` y el segundo no califica (piso 8). Criterio: test verde.
- [ ] Crear `PlayerLeadsRepositoryProtocol` con: muestras por competición del scope (`LeadSample` por jugador, temporada y competición, con posición de contexto ya resuelta), contexto de posición de scope por jugador, y huella de datos (`stamp`) para scope + versión. Criterio: Protocol `runtime_checkable` y Fake de tests que lo satisface.
- [ ] Crear `PlayerLeadsCacheProtocol` con: leer entradas de un jugador, comprobar existencia de snapshot, guardar snapshot completo, adquirir y liberar lock. Criterio: Protocol `runtime_checkable` y Fake.

### 2. Repository

- [ ] Implementar la población base: `player_stats` ⨝ `fixtures` ⨝ `competitions`, fixtures con estado `FT`/`AET`/`PEN`, `minutes > 0`, `player_stats.team_id` no nulo e igual a local o visitante, filtrado por `_scope_filter` sobre las fuentes del scope. Criterio: test PostgreSQL que excluye partido en vivo, fila de 0 minutos y fila con equipo inconsistente.
- [ ] Calcular por fixture los goles de penalti a partir de `player_events` (`goal_penalty`) del mismo jugador y fixture, y derivar `np_goals` y `np_shots_on` con `least`/`greatest` según `decisions.md` antes de sumar. Criterio: test con un penalti marcado (resta en ambos), con más eventos de penalti que goles (cap) y con más goles que tiros a puerta (corrección).
- [ ] Registrar en log por cálculo el número de filas corregidas por `goals > shots_on`. Criterio: test que verifica el contador devuelto/logueado.
- [ ] Calcular la parte "grande": rival = equipo del fixture distinto de `player_stats.team_id`; unir `fixture_team_strengths` del rival por `fixture_id` y `team_id`; fixture grande si `pre_match_strength ≥ 50`, élite si `≥ 70`; `big_minutes`, `big_matches`, `elite_matches` desde `player_stats`; `big_points` = Σ `player_event_scores.final_points` con el `rules_version_id` resuelto en esos fixtures. Si no hay versión, `big_*` a cero y la métrica marcada como no disponible. Criterio: test con rival 49,99 (no cuenta), 50 (cuenta), 70 (élite), sin snapshot (excluido) y puntos de otra versión (ignorados).
- [ ] Resolver la posición de contexto por (jugador, temporada, competición) con `Player.position` + `position_for_context` usando el nombre del equipo verificado más reciente del grupo (mismo criterio que `_latest_verified_team`), y la de scope con el equipo verificado más reciente de clubes del scope. Encapsularlo en un único método privado para sustituirlo cuando 0065 se publique. Criterio: test con override (p. ej. Kimmich en selección → LAT) y jugador sin posición (None).
- [ ] Implementar la huella de datos: `max(last_updated)` y `count(*)` de `sfa_season_scores` filtrado por scope y versión, más `max(fixtures.id)` con estado final del scope, serializados en un string estable. Criterio: test de que cambia al insertar un nuevo `sfa_season_score` o fixture final y no cambia sin escrituras.
- [ ] Verificar en `scoring_repository.py` que el upsert de `sfa_season_scores` actualiza `last_updated` en cada recálculo (también en reescrituras sin cambios de puntos). Si no lo hace, documentarlo en el PR y añadir `count`/`max(id)` suficientes a la huella; no modificar el scoring en este spec. Criterio: nota en el PR con la ruta y línea comprobadas.
- [ ] Devolver solo DTOs de dominio (`LeadSample`, contexto de posición, string de huella), nunca filas ORM. Criterio: revisión de tipos y test.
- [ ] Ejecutar `EXPLAIN (ANALYZE, BUFFERS)` de la consulta de muestras para el award period más grande en un clon. Criterio: tiempo anotado en el PR; presupuesto ≤ 3 s en frío para el cálculo completo del scope.
- [ ] (Condicional) Si se supera el presupuesto, proponer un índice concreto (p. ej. sobre `player_event_scores (rules_version_id, season, competition_id)` o `player_events (fixture_id, player_id, event_type)`) como migración nueva `migrations/00NN_player_leads_indexes.sql` con `CREATE INDEX CONCURRENTLY IF NOT EXISTS`, y repetir la medición. Criterio: medición antes/después en el PR; si no se supera, no se crea migración.

### 3. Cache Redis

- [ ] Implementar `PlayerLeadsCache` sobre `redis.asyncio`: clave `player-leads:{policy_version}:{scope_key}:{rules_version_id|none}:{stamp}`, hash con un campo por `player_id` (JSON de sus entradas) y campo `__meta__` (fecha de cálculo, grupos, jugadores con entradas). Escritura del hash completo y `EXPIRE` de 12 h en una pipeline. Criterio: test que guarda y lee un jugador, y lee vacío para un jugador sin entradas cuando existe `__meta__`.
- [ ] Lock anti-estampida `SET NX` con TTL 120 s en `player-leads-lock:{misma clave}`; liberación solo si el valor del lock coincide con el token propio. Criterio: test de lock adquirido, no adquirido y liberación con token ajeno ignorada.
- [ ] Tratar errores de Redis como fallo de cache (log warning, sin excepción hacia el use case). Criterio: test con cliente que lanza `ConnectionError`.

### 4. Use case

- [ ] `GetPlayerLeadsUseCase.execute(player_id, scope_key, max_rank, limit)`: validar rangos de `max_rank` y `limit` con `LeadPolicy` (`ValueError` fuera de rango). Criterio: tests.
- [ ] Resolver scope con `SeasonRepositoryProtocol.resolve_scope`; `scope_key == "all"` o scope `ALL_TIME` → resultado `supported=false` sin consultas adicionales; sin latest → resultado vacío soportado. `ScopeNotFoundError` se propaga. Criterio: tests con Fakes.
- [ ] Resolver versión con `SFAScoreRepositoryProtocol.resolve_rules_version_id_for_scope`; ante `InconsistentScopeRulesVersionError`, continuar con `rules_version_id=None` y métrica SFA no disponible. Criterio: test que devuelve métricas estadísticas sin `big_game_points_per90`.
- [ ] Obtener huella; si el snapshot existe en cache, leer solo el campo del jugador. Criterio: test donde el repository de muestras no se llama en cache hit.
- [ ] En cache miss: intentar lock; obtener muestras y contexto de scope; ejecutar `PlayerLeadsCalculator`; si se tiene el lock, guardar snapshot y liberar lock; responder desde el snapshot en memoria. Criterio: tests de miss con lock (guarda) y sin lock (no guarda, responde igual).
- [ ] Filtrar entradas del jugador por `rank ≤ max_rank` y cortar a `limit` sin reordenar. Criterio: test con `max_rank=1` y `limit=1`.
- [ ] Logging `[GetPlayerLeadsUseCase]` con scope, versión, hit/miss y duración del cálculo. Criterio: presente en el código y en un test con `caplog`.

### 5. API

- [ ] Añadir schemas Pydantic de respuesta con los campos exactos de "Contrato API" en `decisions.md`. Criterio: test de serialización.
- [ ] Añadir `GET /players/{player_id}/leads` con `scope` opcional, `max_rank` (`ge=1`, `le=3`, por defecto 3) y `limit` (`ge=1`, `le=5`, por defecto 3); `ScopeNotFoundError` → 404. Criterio: tests 200 con items, 200 vacío, 200 `supported=false` para `scope=all`, 404 scope desconocido, 422 `max_rank=4`.
- [ ] Añadir cabecera `Cache-Control: public, max-age=300` en la respuesta. Criterio: test de cabecera.
- [ ] Registrar las factories en `core/dependencies.py`: repository con `AsyncSession`, cache con `get_redis`, use case con `SeasonRepository`, `SFAScoreRepository`, repository, cache y calculator. Criterio: endpoint resuelve dependencias en test de app.
- [ ] Añadir a `http/players.http` peticiones: scope latest, `season-2025`, `world-cup-2026`, `scope=all`, `max_rank=1&limit=1`. Criterio: archivo actualizado.

### 6. Frontend (integración de datos; el diseño visual se trabaja aparte con `impeccable`)

- [ ] Añadir tipos `PlayerLead` y `PlayerLeadsResponse` a `frontend/src/types/index.ts` reflejando el contrato. Criterio: `npm run build` sin errores de tipos.
- [ ] Añadir `fetchPlayerLeads(id, scope)` en `frontend/src/api/client.ts` con la cache de módulo existente y sin petición cuando el perfil está en `season=all`. Criterio: build y revisión.
- [ ] Ocultar la sección cuando `items` esté vacío o `supported=false`; los textos en español se componen en frontend a partir de `metric`, `group` y números (p. ej. "14 de 19 a puerta · 74 % · sin penaltis"; "Ajustado por volumen" cuando `method = wilson_lower_bound`). Criterio: verificación en escritorio y móvil del perfil de un jugador con y sin liderazgos.

### 7. Calidad

- [ ] Escribir tests en `tests/domain/`, `tests/use_cases/`, `tests/repositories/` y API según la lista de archivos a crear.
- [ ] Verificar `pytest tests/` sin fallos ni errores nuevos respecto al baseline y cobertura ≥80 % en cada módulo nuevo y en las líneas modificadas (criterio de 0066).
- [ ] Ejecutar el test PostgreSQL con su variable de entorno contra una base aislada, nunca producción.
- [ ] Verificar `flake8 src/ tests/` sin errores.
- [ ] Verificar `isort --check-only src/ tests/` sin errores.

## Agent Routing Brief

**DDD Designer needed:** yes

La feature introduce un subdominio de lectura nuevo (`domain/player_leads/`) con value objects con invariantes de negocio (`RateCount` con Wilson LB, `LeadSample` con relaciones entre contadores, `PlayerLead` con `rank ≤ qualified_count`), una política versionada de mínimos relativos y un servicio de dominio puro que decide grupos, elegibilidad, empates y "excepcionalidad". Ese modelo ya está fijado en la sección "Domain Model" de `decisions.md` siguiendo la guía de DDD-Designer; el implementador debe respetarlo antes de escribir repository, cache o API. No hay entidades nuevas ni cambios en `domain/scoring/` (sin `ActionType`, multiplicadores ni `BASE_POINTS_TABLE`).

Orden de implementación recomendado: dominio + tests (1) → repository + test PostgreSQL (2) → cache (3) → use case con Fakes (4) → API (5) → frontend de datos (6) → calidad (7). Skills de apoyo: `sfa-repository`, `sfa-use-case`, `sfa-router`, `sfa-test`. No se necesita `sfa-celery-task` en v1.

## Verificación

1. `pytest tests/domain/test_player_leads_models.py tests/domain/test_player_leads_policy.py tests/domain/test_player_leads_calculator.py tests/use_cases/test_get_player_leads.py tests/test_player_leads_api.py` en verde.
2. Con `RANKING_TEST_DATABASE_URL` (o la variable equivalente que defina el test) apuntando a una base aislada: `pytest tests/repositories/test_player_leads_repository_postgres.py` en verde.
3. Local con datos reales: `GET /api/v1/players/{id_raphinha}/leads?scope=season-2025` devuelve `shot_conversion` con numerador/denominador que cuadran con `GET /api/v1/players/{id}/stats?scope=season-2025` (goles y tiros a puerta menos penaltis marcados) y `rank ≤ 3`.
4. Un jugador con muy pocos minutos devuelve `items=[]`; `scope=all` devuelve `supported=false`; `scope=season-1900` devuelve 404; `max_rank=4` devuelve 422.
5. Segunda petición al mismo scope no ejecuta la consulta de muestras (log `hit`) y responde en < 50 ms; la primera (miss) ≤ 3 s en el award period más grande. Tras recalcular scores de una competición del scope, la siguiente petición es `miss` (la huella cambió).
6. Con Redis detenido, el endpoint sigue respondiendo 200 (cálculo directo, warning en log).
7. Comprobación manual de credibilidad: para cada métrica, revisar el top 3 de LaLiga del scope latest y confirmar que ningún líder tiene una muestra ridícula (p. ej. <8 tiros a puerta en eficacia).
