# 0048 - ELO temporal y baseline autoritativo para M1

## Contexto de negocio

El detalle de Dominik Szoboszlai muestra `M1=1.05` contra Bournemouth y `M1=0.99`
contra Leeds. Con la configuracion v2 vigente, M1 no clasifica rivales por nombre o posicion:

`M1 = 1 + (rival_strength - player_strength) / 200`

Por lo tanto, esos valores significan que los datos persistidos colocan a Bournemouth unos
10 puntos de strength (aproximadamente 70 puntos ELO brutos) por encima de Liverpool y a Leeds
solo 2 puntos de strength (aproximadamente 14 puntos ELO) por debajo. La formula de M1 esta
respondiendo a sus inputs; el defecto esta en como se construyen, persisten y leen esos inputs.

El problema afecta a cualquier jugador y fixture recalculado, no solo a Szoboszlai. Un recalculo
de temporada puede reescribir todos los eventos historicos con un ELO terminal incorrecto o con
un baseline sintetico de 1500.

## Auditoria del flujo actual

| Etapa | Implementacion actual | Consecuencia |
|---|---|---|
| Seed ClubElo | `SeedClubEloUseCase` solo acepta entradas `level == 1` y el seed se ejecuta de forma separada al recalculo | Un ascendido, club de copa o equipo no resuelto por nombre puede quedar sin baseline real. |
| Baseline faltante | `CalculateEloRatingsUseCase` ejecuta `initialize_missing_seed_baseline=True` para clubes y asigna `ELO_DEFAULT=1500` antes de comprobar `require_seed_baseline` | La validacion estricta nunca detecta esos faltantes; equipos de niveles muy distintos parten iguales. |
| Persistencia del baseline | El 1500 sintetico se escribe en `team_strengths.elo_seed_raw` junto con `source='club_elo_v2'` | Se pierde la procedencia y el default queda convertido en baseline permanente para futuros replays. |
| Lectura del baseline | `get_all_teams_with_elo` agrupa replicas por competicion usando `MAX(elo_raw)`, `MAX(elo_seed_raw)` y `MAX(strength)` por separado | Si las replicas divergieron, puede construir una combinacion que nunca existio en una fila real. |
| Resultado del fixture | `FixtureRawDTO` trae `home_goals` y `away_goals`, pero `Fixture`, el port y `upsert_fixture` no los persisten | El replay ELO reconstruye el marcador sumando `PlayerStats.goals`; own goals, stats parciales o duplicadas pueden alterar o excluir partidos. |
| Orden del replay | Los fixtures finalizados se ordenan solo por `played_at` | No hay desempate determinista para fixtures con la misma fecha y hora. |
| Estado durante el replay | El use case actualiza ELO en memoria partido a partido, pero solo persiste el estado final | La progresion temporal existe durante el proceso y se descarta al terminar. |
| Proyeccion vigente | `team_strengths` guarda una sola strength terminal por `(team_id, season, competition_id)` | No puede responder cual era el ELO disponible antes de un fixture concreto. |
| Lectura de scoring | `PlayerEventScoreRepository.get_events_for_recalc` une `team_strengths` por equipo, temporada y competicion, sin usar `fixture_id` ni `played_at` | Todos los partidos de la temporada reciben el mismo ELO terminal, incluso los jugados meses antes. |
| Recalculo | `recalculate_award_period_task` completa el replay ELO y luego recalcula toda la temporada | El estado terminal recien persistido se aplica retroactivamente a cada evento historico. |
| Migracion 0045 | `0045_normalize_club_elo_progression.sql` permite `club_elo_v2`, pero no crea seed provenance ni snapshots temporales | La migracion habilita idempotencia terminal, no temporalidad ni cobertura autoritativa. |

La asignacion home/away del repositorio de eventos si es correcta: para un jugador visitante usa
la strength del `away_team` como propia y la del `home_team` como rival. No se debe invertir M1
ni hardcodear que Liverpool es superior a Bournemouth o Leeds. La correccion debe proporcionar
el ELO real, previo al partido y reproducible.

## Restricciones

- Se mantiene Router -> Use Case -> Port -> Repository y el wiring exclusivo en
  `core/dependencies.py`.
- `M1RivalDifficulty`, su divisor y sus clamps no cambian en este spec.
- Clubes y selecciones deben usar el mismo contrato temporal sin mezclar sus pools ni seeds.
- El ELO usado por un fixture debe ser el estado inmediatamente anterior a aplicar su resultado.
- El replay debe ser determinista e idempotente para el mismo seed y conjunto de fixtures.
- Un equipo de una competicion principal no puede recibir 1500 silenciosamente.
- Un score oficial faltante o una cobertura de seed incompleta bloquean el replay; no se publica
  una linea temporal parcial.
- Los replays concurrentes del mismo `(participant_kind, season)` deben serializarse.
- `team_strengths` se conserva como proyeccion del estado vigente para compatibilidad y consultas
  operativas, pero deja de ser la fuente historica de M1.
- Los scores ya calculados no se modifican hasta ejecutar explicitamente el recalculo posterior
  al backfill y a la validacion de cobertura.
- No se accede a `_archive/` ni se usa ORM fuera de infrastructure.

## Invariantes del fix

1. Cada fixture finalizado incluido en ELO tiene exactamente dos snapshots, uno por equipo.
2. `pre_match_elo_raw` se captura antes de aplicar el resultado del propio fixture.
3. M1 lee exclusivamente los dos snapshots del fixture que se esta puntuando.
4. La proyeccion terminal de un equipo coincide con su `post_match_elo_raw` del ultimo fixture
   cronologico del pool.
5. Un replay repetido produce los mismos seeds, snapshots, ELO terminales y M1.
6. Cambiar el resultado de un fixture nunca cambia snapshots anteriores; solo ese fixture y los
   posteriores.
7. Todo baseline y todo marcador poseen procedencia auditable.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Crear `team_elo_seeds` como fuente canonica del baseline | Seguir usando `team_strengths.elo_seed_raw` | Separa estado inicial de proyeccion mutable y conserva fecha, fuente y procedencia. |
| Crear `fixture_team_strengths` con ELO/strength pre y post partido | Agregar solo `effective_at` a `team_strengths` | El join por fixture es inequívoco, evita consultas de rango y permite auditar la transicion completa. |
| Mantener una fila autoritativa por `(fixture_id, team_id)` con `model_version` informativa | Mantener multiples versiones activas y elegir una implicitamente | Evita duplicar eventos en joins. Un cambio de modelo requiere replay explicito y deja su version registrada. |
| Persistir `home_goals`, `away_goals` y `score_source` en `fixtures` | Seguir sumando `PlayerStats.goals` | El marcador oficial ya entra en `FixtureRawDTO` y es la fuente correcta para actualizar ELO. |
| Requerir scores oficiales no nulos para estados `FT`, `AET` y `PEN` usados por ELO | Convertir null a 0-0 | Un empate inventado tambien distorsiona el rating y oculta un problema de ingesta. |
| Re-seedear desde ClubElo a una fecha de corte anterior al primer fixture | Conservar valores 1500 creados por el flujo 0045 | No se puede distinguir de forma fiable un 1500 real de uno sintetico en las filas existentes. |
| Resolver todos los equipos activos presentes en fixtures, sin filtrar `ClubElo.level == 1` | Limitar el snapshot a primera division | Copas y ascendidos tambien necesitan baseline; el scope SFA, no `level`, decide que equipos se requieren. |
| Fallar cerrado si falta seed en el pool | `initialize_missing_seed_baseline=True` | Una temporada parcialmente sembrada produce comparaciones falsas y convierte el fallback en dato permanente. |
| Permitir fallback solo mediante override explicito con source y razon | Default global 1500 | Los equipos sin ClubElo requieren una decision operativa auditable, no una igualdad silenciosa. |
| Ordenar por `(played_at, fixture_id)` y capturar pre-match antes del update | Persistir solo el ELO final | Hace el replay determinista y elimina leakage del resultado del propio partido. |
| Reproducir un pool completo por `participant_kind` | Recalcular solo la liga que disparo la ingesta | El ELO de un club es global y debe incluir liga y copas sin mezclar selecciones. |
| Reemplazar snapshots y proyeccion terminal en una sola transaccion bajo advisory lock comun | Commits parciales y locks distintos por task | Scoring nunca debe observar una linea temporal incompleta o dos replays en carrera. |
| Hacer que scoring falle si falta snapshot temporal luego del cutover | Volver a `team_strengths` terminal o standings | Un fallback silencioso reintroduciria exactamente el defecto auditado. |
| Conservar `team_strengths` como read model terminal | Eliminarla inmediatamente | Mantiene compatibilidad con cobertura/admin y reduce el riesgo de rollout. |
| Registrar en `calculation_details` la version ELO y los valores pre-match | Mostrar solo `m1_source='team_strength'` | Permite explicar y auditar por que un rival produjo un M1 concreto. |

## Domain Model

No se requiere una nueva entidad de negocio ni un nuevo multiplicador. La formula M1 y
`EloCalculatorService` siguen siendo validos. Se agregan DTOs frozen de intercambio y modelos
de persistencia historica.

### DTOs propuestos

- `TeamEloSeedDTO`: `team_id`, `season`, `participant_kind`, `elo_raw`, `effective_at`,
  `source`, `source_reference`.
- `FixtureTeamStrengthDTO`: `fixture_id`, `team_id`, `season`, `competition_id`,
  `pre_match_elo_raw`, `post_match_elo_raw`, `pre_match_strength`,
  `post_match_strength`, `model_version`.
- `EloReplayFixtureDTO`: extiende el contexto del fixture con marcador oficial y orden estable.
- `RebuildEloTimelineResult`: fixtures procesados, equipos actualizados, snapshots escritos,
  coverage y estado.

### Persistencia propuesta

`team_elo_seeds`:

- FK `team_id`.
- `season` y `participant_kind` para separar pools.
- `elo_raw` y `effective_at`.
- `source`, `source_reference` y `created_at` para trazabilidad.
- unique `(team_id, season, participant_kind)`.

`fixture_team_strengths`:

- FK `fixture_id` y FK `team_id`.
- `season`, `competition_id` y `participant_kind` para filtro y auditoria.
- ELO bruto y strength normalizada pre/post partido.
- `model_version`, `seed_source` y `created_at`.
- unique `(fixture_id, team_id)` y check de strength 0-100.
- indices por `(team_id, season, fixture_id)` y `(season, participant_kind)`.

`fixtures` agrega `home_goals`, `away_goals` y `score_source`, nullable durante la transicion.
El use case de replay solo acepta filas finalizadas con ambos goles presentes.

## Flujo objetivo

1. Ingestion persiste equipos, fecha, estado y marcador oficial del fixture.
2. El seed obtiene el snapshot anterior al inicio del periodo, resuelve todos los equipos activos
   del pool y persiste baseline con procedencia.
3. El coordinador toma advisory lock por `(participant_kind, season)`.
4. `RebuildEloTimelineUseCase` valida cobertura total de seeds y scores antes de escribir.
5. Recorre fixtures por `(played_at, fixture_id)`, guarda dos estados pre-match, aplica el
   resultado y completa los estados post-match.
6. En la misma transaccion reemplaza la linea temporal del scope y actualiza `team_strengths`
   con el estado terminal.
7. Tras el commit exitoso, el coordinador ejecuta el recalculo SFA.
8. `PlayerEventScoreRepository` une cada evento con los dos snapshots de su fixture y entrega
   esas strengths a `M1RivalDifficulty`.
9. `player_event_scores.calculation_details` conserva ELO, strength, source y model version.

## Rollout y reparacion de datos

- No se confia en `elo_seed_raw=1500` existente para 2025 porque su procedencia es ambigua.
- Se reingestan o backfillean primero los marcadores oficiales. Las reconstrucciones desde
  eventos solo se aceptan si coinciden con una fuente oficial; `PlayerStats` no es canonico.
- Se descarga ClubElo para una fecha anterior al primer fixture de la temporada y se genera un
  reporte de matched, unmatched y overrides.
- El cutover se bloquea mientras haya equipos o fixtures sin cobertura.
- Se construye la linea temporal completa y se auditan Liverpool, Bournemouth y Leeds antes de
  recalcular puntos.
- Solo despues se recalcula `season-2025`, se reconstruyen bonos/honores y se invalidan caches y
  explicaciones dependientes del ranking.
- La misma infraestructura se aplica al Mundial y futuras temporadas; las selecciones conservan
  su provider y K factor, pero M1 tambien consume snapshots pre-match.

## Integraciones externas

No se agrega un proveedor nuevo.

- ClubElo sigue proporcionando el baseline historico de clubes.
- API-Football sigue proporcionando el marcador oficial a traves de `FixtureRawDTO`.
- National Team ELO sigue proporcionando el baseline de selecciones definido en 0032/0040.
- Si una fuente historica no esta disponible, el proceso produce un reporte bloqueante para
  carga manual autoritativa; nunca sustituye el dato por 1500 o 0-0.
