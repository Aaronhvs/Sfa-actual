# National Team ELO Progression

## Contexto de negocio

El Mundial 2026 ya usa `team_strengths.strength` para alimentar M1 cuando existen strengths
para ambas selecciones. El spec `0032-world-cup-elo-ratings` resolvio el seed inicial desde
ratings externos de selecciones, pero el flujo actual no actualiza ese ELO a medida que se
ingieren partidos del Mundial.

El efecto visible es que una seleccion como Marruecos puede quedar demasiado castigada frente
a Francia si el seed inicial o su normalizacion no refleja el rendimiento mostrado durante el
torneo. La intencion de producto es que exista un ELO base antes del Mundial y que el sistema
lo vaya recalculando con los resultados ya jugados; luego el recalc de scoring debe usar esas
strengths actualizadas para M1.

## Restricciones

- Respetar arquitectura hexagonal: Celery orquesta, Use Case contiene la operacion de negocio,
  Repository escribe/lee DB mediante ports, y scoring sigue consumiendo DTOs/datos de dominio.
- No cambiar la formula de M1 en este spec. El objetivo es actualizar el input de strength, no
  redisenar `M1RivalDifficulty`.
- No crear un camino especial de scoring para Mundial. El recalc debe seguir usando el pipeline
  existente de `run_full_recalculation_task`.
- No perder trazabilidad entre seed inicial y ELO vigente. El sistema debe poder recomputar el
  ELO vigente desde el seed estable y los fixtures finalizados sin compounding accidental.
- No mezclar ELO de clubes y selecciones con una fuente ambigua. Las filas recalculadas de
  selecciones deben usar una fuente auditable distinta de `national_elo_seed`.
- La ingesta puede ejecutarse mas de una vez. El update de ELO + recalc debe ser idempotente
  para un mismo set de fixtures finalizados.
- La cola Celery puede ejecutar tareas concurrentes. El flujo nacional debe evitar carreras
  donde scoring recalcule antes de que ELO haya sido actualizado.
- Para selecciones mundialistas, un seed incompleto no debe caer silenciosamente a ELO 1500;
  debe fallar con auditoria clara antes de recalcular scoring.
- El alcance inicial puede recalcular toda la temporada si ese es el contrato actual de
  `run_full_recalculation_task`, pero el spec debe hacerlo explicito porque afecta operacion.
- Hay cambios parciales no validados en el working tree; la implementacion debe reconciliarlos
  contra este spec antes de continuar.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Preservar el seed inicial en `team_strengths.elo_seed_raw` | Usar solo `elo_raw` como base mutable | Si `elo_raw` se usa como base y destino, reingestas repetidas compounding los mismos fixtures producen ratings distintos. |
| Recalcular ELO nacional desde `elo_seed_raw` + fixtures jugados en orden cronologico | Aplicar delta incremental sobre el ultimo `elo_raw` | El recalculo desde seed hace el flujo idempotente y permite reingestas/rollbacks mas seguros. |
| Agregar source `national_elo_v1` para el ELO vigente del Mundial | Sobrescribir filas con `source='national_elo_seed'` | El seed y el estado progresivo tienen semanticas distintas y deben auditarse por separado. |
| Extender `CalculateEloRatingsUseCase` con parametros de source y baseline de seed | Crear un use case duplicado solo para Mundial | La operacion ELO ya existe; extenderla mantiene una sola regla de calculo y evita bifurcacion innecesaria. |
| Filtrar la lectura baseline de ELO por `competition_ids` cuando se recalcula una competicion | Leer todos los equipos con ELO de la temporada | Evita que ratings de clubes u otras competiciones contaminen un recalculo acotado al Mundial. |
| Crear una tarea Celery coordinadora: ELO nacional y despues recalc de scoring | Encolar `apply_elo_update_task.delay()` y `run_full_recalculation_task.delay()` por separado | Dos tareas independientes tienen carrera: scoring puede correr con strengths viejas. |
| Usar advisory lock transaccional/DB para la secuencia nacional ELO + recalc | Confiar solo en retries de Celery | Dos ingestas simultaneas del Mundial pueden pisarse y producir recalculos intermedios. |
| Mantener `seed_national_team_elo_task` como seed explicito previo | Auto-seed silencioso durante ingestion | Si falta seed o coverage, se debe fallar de forma visible; no conviene inventar defaults en produccion. |
| Bloquear el update nacional si faltan seeds de equipos mundialistas | Permitir fallback automatico a ELO 1500 | Un default silencioso distorsiona justamente los partidos donde M1 debe ser mas confiable. |
| Hacer que ingestion de `participant_kind='national_team'` invoque el coordinador nacional | Saltar ELO como hoy y recalcular directo | El comportamiento actual deja M1 usando un seed estatico o fallback viejo. |
| Auditar la fuente de goles usada para ELO antes de confiar en produccion | Asumir que `PlayerStats.goals` equivale siempre al marcador oficial | ELO debe basarse en resultados oficiales; si se deriva de stats, debe verificarse contra fixtures o migrarse a una fuente oficial disponible. |
| Declarar que el primer coordinador usa el alcance actual de full recalculation por temporada | Prometer recalc acotado por competicion sin soporte del task existente | Evita un contrato falso; un recalc por competition_id puede ser una mejora posterior si el pipeline lo soporta. |

## Domain Model

No se requieren nuevas entidades ni value objects de scoring. El bounded context afectado
sigue siendo scoring, pero el modelo existente ya contiene los conceptos necesarios:

- `team_strengths.strength` representa la fuerza normalizada usada por M1.
- `team_strengths.elo_raw` representa el rating vigente auditable.
- `M1RivalDifficulty` ya consume `player_team_strength` y `rival_team_strength`.
- `EloCalculatorService` ya define expected score, actual score, update y normalizacion.

Se agrega persistencia de baseline (`elo_seed_raw`) como atributo tecnico-auditable en el DTO
`TeamEloRow` y en el modelo `TeamStrength`, pero no como nuevo value object de dominio. No hay
invariantes nuevas que justifiquen `@DDD-Designer`.

### DTOs modificados

- `TeamEloRow(team_id, season, elo_raw, strength, elo_seed_raw)` para transportar el seed
  preservado junto al ELO vigente.

### Protocols modificados

- `TeamStrengthRepositoryPort.upsert_team_elo(...)` acepta `elo_seed_raw` opcional y solo
  actualiza el seed cuando se provee.
- `TeamStrengthRepositoryPort.get_all_teams_with_elo(...)` acepta `competition_ids` opcional
  para leer baseline acotado a la competicion recalculada.

## Integraciones externas

No se agrega una nueva integracion externa. El seed inicial sigue usando el provider existente
de selecciones definido por el spec `0032-world-cup-elo-ratings`.

El update progresivo usa solo datos internos ya ingeridos:

- `fixtures` para equipos, competicion, temporada y fecha.
- `player_stats` y snapshots/equipo resuelto para reconstruir goles del fixture.
- `team_strengths` para seed inicial y escritura de ELO/strength vigente.
