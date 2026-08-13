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

## Extension 0048-A - Resolucion historica individual de ClubElo

Esta extension pertenece a 0048 y no requiere un spec nuevo. No cambia la formula ELO, M1, el
modelo de replay ni el significado de `team_elo_seeds`; completa la obtencion del baseline
autoritativo que 0048 ya exige. Separarla en otro spec permitiria implementar el replay temporal
sin cerrar el gate de seeds que forma parte del mismo contrato.

### Hallazgo posterior al rollout

El dry-run del seed de clubes 2025 resolvio 258 de 356 equipos desde el snapshot diario y dejo 98
equipos sin seed. La lectura del flujo implementado confirma estas limitaciones:

- `ClubEloProvider` solo expone `fetch_snapshot(date_str)`; no consulta el historial individual.
- `ClubEloEntry` y `_parse_csv` descartan las columnas `From` y `To` que ClubElo ya entrega.
- `SeedClubEloUseCase` pasa directamente de snapshot diario a `manual_override`.
- El provider se inyecta sin un Protocol de dominio y el use case no puede expresar un contrato
  tipado de historial, evidencia o errores por club.
- El fuzzy matching puede producir sugerencias utiles, pero no constituye evidencia suficiente
  para asociar automaticamente dos identidades de club.
- `team_elo_seeds.source_reference` no permite consultar de forma estructurada identidad,
  intervalo, antiguedad y checksum del payload usado.
- El endpoint no ofrece dry-run ni un reporte por equipo antes del apply.

ClubElo expone dos recursos CSV del mismo proveedor:

- `GET http://api.clubelo.com/{YYYY-MM-DD}`: snapshot diario.
- `GET http://api.clubelo.com/{club_identifier}`: historial individual con
  `Rank,Club,Country,Level,Elo,From,To`.

El segundo recurso se verifico contra identificadores reales y contiene intervalos historicos
individuales. Se acepta como la misma fuente autoritativa de 0048, pero solo bajo las reglas de
identidad, temporalidad y antiguedad siguientes.

### Definiciones temporales

- `cutoff`: fecha UTC inmediatamente anterior al primer fixture del pool club/season. El servidor
  la deriva desde fixtures y exige que `date_str` coincida con ella; no confia solo en el caller.
- `source_valid_from`: valor `From` de la fila individual de ClubElo.
- `source_valid_to`: valor `To` de la fila individual de ClubElo.
- `history_age_days`: `max(0, cutoff - source_valid_to)` en dias calendario.
- `exact_at_cutoff`: `source_valid_from <= cutoff <= source_valid_to`.
- `prior_carry_forward`: `source_valid_to < cutoff` y `history_age_days <= 365`.

El limite maximo es **365 dias calendario** y forma parte del modelo de seed, no de un parametro
HTTP ni de una setting mutable. Exactamente 365 dias se acepta; 366 se rechaza. El limite permite
usar la ultima temporada competitiva conocida y rechaza un rating sin actividad ClubElo durante
mas de un ciclo anual completo. Cambiarlo requiere una nueva decision y un nuevo model version.

Decision operativa cerrada para el cutoff `2025-07-07`:

| Equipos auditados | Gap desde `To` | Decision automatica |
|---|---:|---|
| Cardiff, Eldense, Regensburg | 2 dias | Aceptar como `clubelo_history_prior`. |
| Concarneau, Rostock, Huddersfield, Wehen | 367 dias | Rechazar por stale; requieren `manual_override`. |
| Sochaux, Wigan, Sandhausen | 737 dias | Rechazar por stale; requieren `manual_override`. |
| Cualquier otro historial mas antiguo | Mayor a 737 dias | Rechazar por stale; requieren `manual_override`. |

`max_staleness_days = 365` es inclusivo. No se redondea por temporada ni se concede tolerancia
adicional: un gap de 367 dias no se reduce a "una temporada". El valor tampoco se amplía para
obtener coverage; coverage se completa con evidencia manual cuando el historial queda fuera del
limite.

Para un historial individual se consideran solo filas con ELO positivo, fechas parseables,
`From <= To` y `From <= cutoff`. Se elige la fila con mayor `From`. Si varias filas tienen ese
mismo `From`, solo se deduplican cuando identidad, pais, ELO y `To` son identicos; cualquier
conflicto es ambiguo y bloquea. Una fila futura nunca puede influir en la seleccion.

### Autoridad de identidad

Una fila historica es autoritativa para un equipo SFA solo cuando se cumplen todas estas reglas:

1. El identificador individual proviene de un registro de identidad versionado y explicito que
   relaciona `sfa_team_name`, `clubelo_identifier` y `expected_country`.
2. La respuesta conserva el club y el pais esperados por ese registro.
3. La identidad no depende de similitud difusa, substring, orden de candidatos ni de que exista
   una sola sugerencia en ese momento.
4. El historial pasa las validaciones temporales y de antiguedad.
5. La referencia, intervalo y checksum del payload quedan persistidos con el seed.

El catalogo existente de aliases se normaliza a registros bidireccionales y univocos. Los aliases
exactos o normalizados unicos pueden resolver el snapshot diario; para abrir un endpoint
individual se exige ademas un `clubelo_identifier` explicito. Casos ambiguos como `Lincoln` no se
resuelven sin pais. El fuzzy matching se conserva exclusivamente como sugerencia en el reporte de
auditoria y nunca incrementa `matched` ni habilita escrituras.

### Precedencia de resolucion

Para cada equipo requerido se aplica este orden, sin mezclar valores:

1. `clubelo_snapshot`: fila valida del snapshot del cutoff resuelta por identidad exacta,
   normalizada unica o alias verificado.
2. `clubelo_history`: historial individual cuya fila cubre el cutoff.
3. `clubelo_history_prior`: ultima fila individual anterior, con antiguedad entre 1 y 365 dias.
4. `manual_override`: fallback explicito para un equipo que sigue sin historial fiable.

El historial individual solo se consulta para equipos ausentes del snapshot, no para sustituir
un valor diario valido. Una entrada manual solo completa un equipo aun irresuelto; no sobreescribe
un snapshot o historial autoritativo dentro de este flujo. Un override deliberado sobre una
fuente automatica requiere una operacion distinta y queda fuera de 0048-A.

### Fallback manual

`ManualClubEloEntry` deja de ser solo nombre, valor y texto libre. Para ser aceptada como fallback
debe incluir:

- `team_name` exacto y unico dentro del pool.
- `elo_raw` positivo.
- `reason` no vacio que explique el criterio de asignacion.
- `source_reference` no vacio, trazable a documento, consulta o ticket de aprobacion.
- `source_date` parseable y no posterior al cutoff.
- `approved_by` no vacio para trazabilidad operativa.

Entradas duplicadas, equipos ajenos al pool, valores sin evidencia o intentos de reemplazar una
resolucion automatica son blockers. El valor manual no hereda la tolerancia de 365 dias: su
autoridad procede de una decision explicita y debe declarar su fecha y razon. La API lo etiqueta
siempre como `manual_override`; nunca como ClubElo.

### Ports y DTOs

Se agrega `ClubEloProviderPort` en dominio para que application no dependa de una clase concreta.
El port ofrece el snapshot y los historiales individuales; HTTP, CSV, retries, URL encoding y
checksums quedan dentro del adapter.

DTOs frozen requeridos:

- `ClubEloRatingDTO`: club, country, level, elo, valid_from y valid_to.
- `ClubEloSourceDTO`: referencia, fecha de fetch, SHA-256 del payload y ratings parseados.
- `ClubEloIdentityDTO`: nombre SFA, identificador ClubElo y pais esperado.
- `EloSeedProvenanceDTO`: resolution method, source entity, country, valid interval, age,
  source reference y payload checksum.
- `ClubEloSeedResolutionDTO`: resultado por equipo (`snapshot`, `history`, `manual`,
  `unresolved`, `stale`, `ambiguous`, `provider_error`) y evidencia disponible.

No se crea una entidad de negocio ni un value object del dominio futbolistico. Estos DTOs
formalizan una integracion y la evidencia de un dato tecnico existente.

### Persistencia de procedencia

Como `0048_temporal_elo_m1.sql` ya fue desplegada, no se reescribe. Una migracion aditiva 0049
agrega `provenance_json JSONB NOT NULL DEFAULT '{}'` a `team_elo_seeds`, con check de que sea un
objeto. `source_reference` se mantiene como locator corto e indexable; el JSONB guarda la
evidencia estructurada sin sobrecargar ese varchar.

Para sources ClubElo, `provenance_json` exige como minimo:

- `resolution_method`, `source_entity`, `source_country`;
- `source_valid_from`, `source_valid_to`, `history_age_days`;
- `cutoff`, `source_reference`, `payload_sha256`.

Para `manual_override` exige `reason`, `source_reference`, `source_date` y `approved_by`. El
repositorio persiste y reconstruye el DTO de procedencia; no expone JSON o modelos ORM al use
case. `effective_at` sigue siendo el cutoff aplicado al seed, mientras el intervalo original vive
en provenance. Seeds club legacy con provenance vacia no satisfacen el nuevo gate y deben
resembrarse; seeds de selecciones no quedan sujetos a las claves especificas de ClubElo.

### Flujo objetivo extendido

1. El use case obtiene el conjunto requerido y el primer fixture mediante el repository port.
2. Valida season, cutoff derivado, manual entries y duplicados antes de llamar al provider.
3. Descarga y valida el snapshot diario completo.
4. Resuelve identidades autoritativas; guarda fuzzy candidates solo para diagnostico.
5. Para cada ausente con identidad individual verificada, obtiene su historial una sola vez.
6. Selecciona la ultima fila elegible anterior al cutoff y aplica el gate de 365 dias.
7. Aplica manual fallbacks solo a los equipos que continuan irresueltos.
8. Construye un reporte completo con conteos por source y blockers por equipo.
9. En dry-run retorna el reporte y no escribe aunque exista 100% de cobertura.
10. En apply exige cero blockers y 100% de cobertura antes del primer upsert.
11. Router o task hace un unico commit; cualquier excepcion revierte seeds y proyecciones.

No se publica seed parcial. Un timeout, 429, 5xx, CSV malformado o historial ambiguo impide el
apply completo. Un 404 o historial vacio se clasifica `no_history` y puede resolverse manualmente.

### Contrato HTTP administrativo

Se conserva `POST /api/v1/admin/elo/seed`; no se crea un endpoint paralelo.

- `dry_run` pasa a ser `true` por defecto. Persistir requiere `dry_run=false` explicito.
- La respuesta agrega `cutoff`, `total_teams`, conteos por source, `coverage_pct`,
  `history_requests`, `blockers` y `resolutions` por equipo.
- Coverage incompleta, historia obsoleta, identidad ambigua o manual entry invalida retornan 422.
- Indisponibilidad o respuesta invalida del provider retorna 503.
- Un dry-run con blockers retorna el reporte completo sin esconderlo dentro de un string.
- El router solo traduce resultado/excepciones y controla commit/rollback; no selecciona filas ni
  calcula antiguedad.

### Limites del adapter externo

- El host ClubElo es constante y no se acepta una URL arbitraria desde el request.
- Los identificadores se percent-encodean y no se siguen redirects fuera del host permitido.
- Los historiales se deduplican por identificador y se consultan con concurrencia maxima de 5.
- Timeout, 429 y 5xx permiten un unico retry acotado; 404 y CSV vacio no se reintentan.
- Cada payload se hashea antes del parseo y el hash se conserva en el DTO de source.
- Los datos se cargan y validan por completo antes de cualquier escritura de DB.

El API disponible es HTTP y no ofrece autenticacion. Esta limitacion de transporte se registra
como riesgo aceptado del provider existente; el allowlist de host, el checksum persistido y el
dry-run reducen sustituciones accidentales, pero no convierten HTTP en transporte autenticado.
Si ClubElo habilita HTTPS, el adapter debe migrar sin cambiar el port.

### Invariantes adicionales

8. Ningun seed historico usa una fila con `From` posterior al cutoff.
9. Ningun seed automatico usa un historial con `history_age_days > 365`.
10. Todo seed de club aplicado tiene provenance estructurada y una resolution method reconocida.
11. Un fuzzy candidate nunca se convierte en seed sin promoverse antes al catalogo verificado.
12. El mismo snapshot, catalogo, historiales, manual manifest y cutoff producen los mismos seeds.
13. Agregar una fila futura al historial no cambia el seed de un cutoff anterior.
14. Un apply con un solo blocker deja intactos todos los seeds y snapshots existentes.

### Rollout de la extension

- Desplegar primero la migracion aditiva y el flujo dry-run; no ejecutar replay ELO aun.
- Ejecutar dry-run club/2025 y revisar separadamente snapshot, history, stale, no-history,
  ambiguous y provider-error.
- Incorporar al catalogo solo identidades comprobadas contra ClubElo y repetir dry-run.
- Preparar un manifest manual con evidencia para los clubes restantes.
- Ejecutar apply solo con 356/356, cero blockers y provenance completa.
- Verificar seeds por source y auditar valores extremos antes de construir la linea temporal.
- Recién entonces continuar el replay y recalculo definidos por 0048.
