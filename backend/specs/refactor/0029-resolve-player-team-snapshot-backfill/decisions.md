# 0029 - Recuperacion auditable de snapshots de equipo unresolved

## Contexto

El spec 0028 agrego snapshots inmutables de equipo en `player_stats.team_id` y
`player_events.team_id`. La migracion 0021 fue probada sobre una copia de la DB y
resolvio la mayoria de las filas mediante fuentes locales, pero quedaron:

- 20.728 filas de `player_stats` sin `team_id`.
- 24.047 filas de `player_events` sin `team_id`.
- 0 snapshots fuera de los equipos del fixture.
- 0 divergencias entre eventos y apariciones resueltas.
- 0 eventos sin `player_stats`.

Mientras existan snapshots unresolved no se puede ejecutar 0022 ni habilitar la ingesta
del Mundial.

## Diagnostico confirmado - 2026-06-13

Consultas de solo lectura sobre la DB activa, todavia sin 0021, reprodujeron ambos
candidatos del backfill:

- 21.711 filas no coinciden con `players.team_id`.
- 1.510 jugadores y 3.982 fixtures estan afectados.
- 983 filas tienen candidato valido en `sfa_season_scores`.
- El residual final es exactamente 20.728 filas.
- Ninguna discrepancia se debe a `players.team_id IS NULL`.
- 19.942 filas residuales, en 2.732 scopes jugador/temporada/competicion, repiten un
  mismo equipo del fixture en el 100% de sus partidos. El patron es consistente con
  transferencias.
- Otras 779 filas son compatibles principalmente con transferencias dentro de una
  temporada y requieren asignacion exacta por fixture.
- Siete filas residuales pertenecen a `players.id=202854`, Brando Bettazzi, cuyo
  `external_id=0`. Sus fixtures no comparten un equipo historico coherente.

Conclusion: la causa A domina, pero existe una causa B de identidad invalida. No es
seguro resolver todas las filas mediante una unica heuristica SQL.

## Problema del flujo existente

`ReingestPlayerUseCase` y `BackfillFixtureStatsUseCase` no pueden resolver este conjunto:

- `get_fixtures_for_player()` excluye apariciones cuyo `player_stats.team_id` es NULL.
- `fetch_all_fixture_players()` aplana la respuesta del proveedor y pierde el equipo
  asociado a cada jugador.
- La reingesta actual elimina y reconstruye eventos y recalcula scores. Eso tiene un
  alcance mayor al necesario y aumenta el riesgo de modificar datos historicos.
- No existe un registro persistente de intentos, decisiones, errores ni filas reparadas.

## Objetivo

Crear un flujo operativo que recupere exclusivamente la identidad de equipo por
aparicion, de forma:

- deterministica;
- auditable;
- reanudable;
- idempotente;
- limitada por temporada, competicion y cantidad de fixtures;
- segura frente a limites o fallos de API-Football;
- incapaz de modificar estadisticas, eventos de scoring o puntos.

## Fuera de alcance

- No recalcular puntos, bonos, ELO ni logros.
- No volver a ingestar partidos completos.
- No modificar formulas o multiplicadores.
- No inferir equipos mediante similitud aproximada de nombres.
- No aplicar 0022 automaticamente.
- No habilitar la ingesta del Mundial.
- No corregir jugadores duplicados ni identidades sin `external_id`.
- No introducir afiliaciones temporales de jugadores.

La identidad invalida conocida queda en cuarentena y requiere una correccion manual
auditada antes del gate de 0022. No participa en la reparacion automatica.

## Fuente de verdad

Para cada fixture unresolved se consulta una sola vez la respuesta de jugadores del
fixture en API-Football conservando esta relacion:

`fixture_external_id -> team_external_id -> player_external_id`

La asignacion se acepta solo cuando:

1. El `player_external_id` coincide exactamente con `players.external_id`.
2. El `team_external_id` coincide exactamente con el external ID del home o away local.
3. El equipo local resultante es `fixtures.home_team_id` o `fixtures.away_team_id`.
4. El jugador aparece bajo un unico equipo dentro de la respuesta del fixture.

Si cualquiera de estas condiciones falla, la fila permanece unresolved.

Los jugadores con `external_id IS NULL` o `external_id <= 0` nunca son candidatos para
reparacion automatica. Se registran como `invalid_player_external_id`.

## Estrategia de resolucion

### Unidad de trabajo

La unidad de trabajo es el fixture, no el jugador. Un request al proveedor puede resolver
todas las apariciones unresolved del mismo partido y evita consumir la cuota una vez por
jugador.

### Fases

1. Seleccionar fixtures con al menos un `player_stats.team_id IS NULL`.
2. Registrar un run persistente con filtros, modo y contadores iniciales.
3. Consultar API-Football una vez por fixture.
4. Construir candidatos exactos por `player_external_id`.
5. En dry-run, registrar decisiones sin actualizar snapshots.
6. En apply, actualizar `player_stats.team_id` solo para candidatos validos.
7. Propagar el equipo a todos los `player_events` del mismo `(player_id, fixture_id)`.
8. Registrar resultado individual: resolved, already_resolved, provider_missing,
   invalid_player_external_id, team_not_in_fixture, ambiguous o provider_error.
9. Ejecutar los cinco contadores criticos al finalizar cada lote.

## Prevencion de identidades invalidas

Antes del repair se impide crear o actualizar jugadores con `external_id <= 0`:

1. El adaptador de API-Football descarta y registra players sin ID positivo.
2. El use case de ingesta valida el ID antes de invocar `upsert_player`.
3. El repositorio rechaza defensivamente IDs no positivos.
4. Tras corregir el dato existente se valida el check
   `players.external_id IS NULL OR players.external_id > 0`.

La fila existente con ID cero no se renombra ni reasigna en bloque. Sus fixtures se
comparan con API-Football para identificar al jugador real; stats y eventos se mueven o
eliminan mediante una correccion manual auditada.

## Persistencia operativa

Se agregan dos tablas de soporte. No forman parte del dominio de scoring.

### `team_snapshot_repair_runs`

Registra:

- modo `dry_run` o `apply`;
- filtros de temporada y competicion;
- limite de fixtures y tamano de lote;
- estado `pending`, `running`, `completed`, `partial` o `failed`;
- fixture cursor para reanudar;
- contadores iniciales y finales;
- timestamps y error global.

### `team_snapshot_repair_items`

Registra una fila por aparicion inspeccionada:

- run;
- `player_stats_id`, `player_id` y `fixture_id`;
- equipo anterior y candidato;
- fuente `api_football_fixture_players`;
- estado y razon;
- payload minimo de evidencia: external IDs, nunca la respuesta completa;
- timestamp.

Una restriccion unica por `(run_id, player_stats_id)` hace el procesamiento idempotente.

## Contratos de dominio

Se crea un port operacional separado de `IngestionRepositoryPort`:

`TeamSnapshotRepairRepositoryPort`

Responsabilidades:

- crear y finalizar runs;
- adquirir trabajo unresolved por fixture;
- recuperar mapas locales de equipos y jugadores;
- aplicar un snapshot validado;
- propagarlo a eventos;
- registrar items;
- obtener los cinco contadores criticos.

DTOs frozen:

- `UnresolvedFixtureDTO`
- `UnresolvedAppearanceDTO`
- `FixturePlayerTeamRawDTO`
- `SnapshotRepairDecisionDTO`
- `SnapshotAuditCountsDTO`
- `TeamSnapshotRepairResult`

No se extiende el port de ingesta porque la reparacion es un proceso operacional
independiente y temporal.

## Provider

Se agrega al port de API-Football una operacion que preserve el equipo de cada jugador.
El adaptador devuelve DTOs planos con `fixture_external_id`, `team_external_id` y
`player_external_id`.

No se reutiliza `fetch_all_fixture_players()` porque su contrato actual descarta el
equipo y cambiarlo seria incompatible con los consumers existentes.

## Use case

`RepairPlayerTeamSnapshotsUseCase`

Parametros:

- `dry_run`, default verdadero;
- `season`, opcional;
- `competition_id`, opcional;
- `max_fixtures`, obligatorio con limite conservador;
- `batch_size`;
- `resume_run_id`, opcional.

Invariantes:

- `apply` requiere confirmacion explicita en la capa de entrada.
- No procesa competiciones `national_team`.
- No sobrescribe snapshots no nulos.
- No acepta un candidato fuera del fixture.
- No actualiza `player_events` si `player_stats` no fue resuelto.
- Cada lote se confirma en una transaccion independiente.
- Un error de proveedor marca el fixture como pendiente y permite continuar.

## Ejecucion

La ejecucion real se hace mediante Celery:

- evita mantener una request HTTP abierta;
- permite reintentos por errores transitorios;
- controla el numero de fixtures por corrida;
- facilita pausas por cuota del proveedor.

Se agrega un endpoint administrativo para iniciar el task y endpoints de lectura para
consultar el run y su auditoria. Estos endpoints deben quedar protegidos por el mismo
mecanismo administrativo que se defina para el despliegue VPS; no deben exponerse
publicamente sin autenticacion.

## Concurrencia

Solo puede existir un run `apply` activo. Se usa un advisory lock de PostgreSQL durante
la adquisicion de lotes y una restriccion operacional que impida dos runs activos.

Los dry-runs pueden ejecutarse en paralelo porque no escriben snapshots, pero deben tener
su propio registro de run.

## Cuota y reanudacion

- El cursor persistente es el ultimo `fixture_id` inspeccionado.
- El siguiente lote comienza despues del cursor.
- `max_fixtures` limita requests por corrida.
- Los errores 429 o de red dejan el run en `partial`, conservan cursor y permiten resume.
- Reanudar no vuelve a procesar items ya registrados para el run.

## Seguridad de datos

Antes de cada apply se captura un baseline:

- filas y suma de `sfa_season_scores.total_pts`;
- suma de `achievement_bonus_pts`;
- hash ordenado de scores por jugador, competicion, temporada y rules version;
- conteos de eventos y stats.

Al finalizar:

- los baselines deben permanecer identicos;
- solo pueden cambiar `player_stats.team_id`, `player_events.team_id` y tablas de repair;
- cualquier diferencia invalida el run y bloquea 0022.

## Criterio para ejecutar 0022

El flujo de repair no ejecuta 0022. Solo produce evidencia para autorizarla.

Condiciones:

1. Cinco contadores criticos exactamente en cero.
2. Ningun run apply en estado running, partial o failed sin revisar.
3. Baseline de scores y bonos identico.
4. Reingesta de muestra de La Liga sin diferencias de puntos.
5. ELO y logros comparados contra baseline.
6. Codigo nuevo desplegado y callers antiguos detenidos.

## Rollback

El apply es reversible usando `team_snapshot_repair_items`:

- solo se revierten filas cuyo valor actual coincide con el candidato aplicado por el run;
- se restaura el valor anterior registrado;
- los eventos se restauran desde el valor anterior de la aparicion;
- el rollback genera un nuevo run de tipo rollback, nunca borra evidencia.

Como los valores anteriores esperados son NULL, el rollback no toca snapshots resueltos
por procesos posteriores.

## Decisiones descartadas

| Alternativa | Motivo |
|---|---|
| Reingestar todos los fixtures completos | Puede modificar stats, eventos y scores; consume mas cuota. |
| Procesar por jugador | Multiplica requests para un mismo fixture. |
| Inferir por nombre | Riesgo de falsos positivos y homonimos. |
| Asignar siempre home o away por descarte | No existe evidencia suficiente. |
| Resolver directamente con SQL manual | No es reanudable ni conserva evidencia por decision. |
| Ejecutar 0022 al terminar el task | El constraint requiere validacion operativa externa. |
| Guardar solo logs de texto | No permite consulta, rollback ni reanudacion fiable. |

## Resultado esperado

El sistema puede reducir de forma controlada los snapshots unresolved hasta cero sin
cambiar ningun punto existente. Las filas que API-Football no pueda resolver quedan
identificadas individualmente para una correccion manual auditada. Solo entonces se
autoriza 0022 y, posteriormente, la ingesta aislada del Mundial.
