# 0028 - Afiliaciones de jugador y snapshots de equipo por aparicion

## Contexto de negocio

API-Football identifica globalmente a un jugador con el mismo `external_id` aunque participe
para entidades deportivas distintas. Pedri usa `external_id=133609` tanto con Barcelona
como con Espana. La restriccion `UNIQUE` de `players.external_id` evita duplicar su
identidad, pero el modelo actual obliga a guardar un unico `players.team_id`.

`IngestionRepository.upsert_player()` sobrescribe ese campo en cada aparicion. Ingerir el
Mundial 2026 reemplazaria Barcelona por Espana y convertiria un dato contextual del partido
en estado global mutable. ELO, logros, reconstruccion de scores, rankings, perfiles y
reingestas todavia leen ese estado global.

Este refactor separa:

- identidad global: `Player`;
- afiliacion observada durante una temporada: `PlayerTeamAffiliation`;
- equipo inmutable de una aparicion: `player_stats.team_id`;
- equipo inmutable de un evento: `player_events.team_id`.

## Restricciones

- `players.external_id` permanece `UNIQUE` y es la identidad global autoritativa.
- No se modifican formulas, multiplicadores, puntos base ni bonus de scoring.
- Todo snapshot de aparicion o evento debe ser `fixtures.home_team_id` o
  `fixtures.away_team_id`.
- `sfa_season_scores.team_id` sigue siendo un snapshot de presentacion por
  jugador-competicion-temporada-version, no la fuente de verdad por partido.
- Los contratos HTTP existentes mantienen `team_name` y `team_logo_url`.
- Ninguna fila ambigua puede recibir un equipo arbitrario.
- El Mundial 2026 queda fuera de este spec.
- `players.team_id` no se elimina fisicamente en este spec.

## Mapa del comportamiento actual

| Superficie | Dependencia actual | Riesgo |
|---|---|---|
| Ingestion | `upsert_player` sobrescribe `Player.team_id` | La seleccion reemplaza al club |
| Estadisticas | `PlayerStats` no conserva `team_id` | No existe atribucion historica segura |
| Eventos | `PlayerEvent` no conserva `team_id` | Goles y tandas dependen del equipo global |
| Reingesta | Usa `Player.team_id` | Puede invertir local y visitante |
| ELO | Separa goles con `Player.team_id` | El estado acumulativo puede estar historicamente contaminado |
| Logros | Filtra jugadores y minutos por `Player.team_id` | Bonus atribuido al equipo incorrecto |
| Rebuild | Copia `players.team_id` a `sfa_season_scores` | Reescribe snapshots historicos |
| Ranking y perfil | Usa fallback global mutable | Muestra un equipo fuera de contexto |

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Mantener `Player` como identidad global sin equipo autoritativo | Un jugador por club y otro por seleccion | Los puntos deben acumularse bajo un unico `player_id`. |
| Crear `PlayerTeamAffiliation` por jugador-equipo-temporada-tipo | Conservar un unico equipo actual | Club y seleccion pueden coexistir y un jugador puede transferirse. |
| Agregar `team_id` a `player_stats` | Inferir desde afiliacion actual | La aparicion requiere contexto historico inmutable. |
| Agregar `team_id` a `player_events` | Derivarlo siempre con un join | El evento de scoring debe ser auditable por si mismo. |
| Tratar la divergencia evento-aparicion como error critico | Aceptar snapshots independientes | Para un mismo jugador y fixture ambos deben representar el mismo equipo. |
| Dejar de escribir `players.team_id` | Priorizar club o seleccion | Cualquier equipo unico pierde informacion. |
| Persistir `competitions.participant_kind` con default `club` | Conservarlo solo en `LeagueConfig` | La semantica debe poder validarse en DB y en auditorias operativas. |
| Permitir `AffiliationKind` `club` y `national_team` | Inferirlo por nombre o pais | Evita heuristicas y hace auditable el vinculo. |
| Usar solamente `source=fixture` en este spec | Introducir tambien `squad` | No existe aun un flujo de plantillas que produzca evidencia `squad`. |
| Derivar scores, ELO y logros desde apariciones/eventos | Usar afiliaciones nominales | Las reglas historicas deben basarse en participacion real. |
| Mantener `players.team_id` nullable y deprecado durante rollout | Borrarlo en expand | Permite dual-read temporal y rollback de aplicacion. |
| Separar expand/backfill y constraints | Una migracion transaccional larga | Permite pausar, auditar y corregir antes de imponer `NOT NULL`. |

## Respuestas formales P1-P5

### P1 - Equipo mostrado en ranking global

La regla no usa una "competicion principal".

Para cada jugador y alcance solicitado, el equipo representativo es:

1. agrupar `player_stats` por `team_id` dentro del alcance;
2. elegir el equipo con mayor suma de `minutes`;
3. si hay empate, elegir el de la aparicion con `fixtures.played_at` mas reciente;
4. si persiste el empate, elegir el menor `team_id`.

Alcances:

- ranking por competicion: solo esa competicion y temporada;
- ranking global de temporada: todas las competiciones de la temporada;
- ranking historico sin temporada: primero la temporada con aparicion mas reciente y luego
  aplicar la misma regla dentro de esa temporada.

La regla se implementa una sola vez como resolver de lectura compartido por ranking,
detalle y rebuild. Para Pedri en un ranking global 2025/26 se mostrara Barcelona o Espana
segun cual acumule mas minutos en ese alcance, no segun el ultimo proceso de ingestion.

### P2 - Recalculo ELO post-backfill

El ELO se recalcula completamente para cada temporada afectada. No se acepta el estado
actual como baseline porque es acumulativo y pudo usar goles atribuidos al lado incorrecto.

Procedimiento obligatorio:

1. determinar temporadas afectadas por snapshots creados o corregidos;
2. generar y guardar un artefacto de baseline por
   `season + team_id + baseline_date + elo_raw + source`;
3. para clubes, regenerar el baseline con el flujo ClubElo existente usando una fecha
   configurada anterior al primer fixture de la temporada;
4. equipos sin seed reproducible comienzan en `ELO_DEFAULT=1500`;
5. validar que el artefacto cubre todos los equipos o documenta explicitamente los defaults;
6. eliminar o reemplazar solamente resultados calculados `source=elo_v1` de la temporada;
7. reproducir todos los fixtures afectados en orden
   `played_at ASC, fixture_id ASC` usando `player_stats.team_id`;
8. persistir el resultado y comparar fixtures, goles y equipos procesados con la auditoria;
9. ejecutar despues el recalculo completo de scoring para las versiones activas que
   consuman M1.

Si no puede producirse un baseline reproducible, el cutover y el gate del Mundial quedan
bloqueados. El artefacto pre-rollout sirve para comparacion, no como seed inicial.

### P3 - Filas sin resolver

Antes de expand se ejecuta `scripts/audit_player_team_snapshots.sql` en modo diagnostico
sobre una copia actual de la DB. Deben registrarse:

- total de stats y eventos;
- resolubles por snapshot de score;
- resolubles por `players.team_id`;
- conflictos informativos;
- stats sin resolver;
- eventos sin aparicion;
- divergencias evento-aparicion;
- equipos fuera del fixture;
- afiliaciones con semantica invalida.

El conteo inicial puede ser mayor que cero y define el trabajo operativo. Para constraints,
cutover y Mundial, todos los contadores criticos deben ser exactamente cero. No existe
umbral parcial aceptable.

### P4 - Multiples afiliaciones club

Si. Una transferencia puede producir varias afiliaciones `club` en la misma temporada.
No existe concepto de "afiliacion activa unica" en este spec. Los intervalos
`first_seen_at` y `last_seen_at` describen evidencia observada, no contratos laborales. La
UI contextual usa apariciones; el perfil sin contexto aplica el fallback formal definido
mas abajo.

### P5 - Criterio critico de auditoria

Bloquean constraints, cutover y Mundial:

- `player_stats.team_id IS NULL`;
- `player_events.team_id IS NULL`;
- snapshot fuera de los dos equipos del fixture;
- evento sin `player_stats` para el mismo `(player_id, fixture_id)`;
- `player_events.team_id <> player_stats.team_id`;
- score sin equipo representativo resoluble;
- afiliacion sin aparicion que la respalde;
- `kind` distinto de `competitions.participant_kind` para la evidencia que la creo;
- filas duplicadas contra las claves unicas definidas.

## Domain Model

### Revision DDD-Designer

El criterio local de DDD distingue Entity, Value Object y Aggregate por identidad e
invariantes protegidas. Aplicado a este caso:

- `PlayerTeamAffiliation` es Entity porque tiene identidad persistida e intervalo mutable.
- `PlayerFixtureAppearance` es un concepto de dominio con identidad compuesta
  `(player_id, fixture_id)`, persistido dentro de `player_stats`.
- `AffiliationKind` es Value Object inmutable.
- `AffiliationSource` no se modela como Value Object en este spec: el unico valor permitido
  es la constante persistida `fixture`.
- `PlayerParticipation` se elimina. No hay una invariante transaccional que requiera una
  raiz comun para afiliaciones y apariciones; el caso de uso coordina ambos ports dentro de
  la misma transaccion.

### Bounded context

Subdominio `participation` dentro de `domain/`. Scoring consume snapshots de participacion,
pero no posee estas entidades ni modifica sus formulas.

### Entidades

- `PlayerTeamAffiliation(id, player_id, team_id, season, kind, first_seen_at,
  last_seen_at, source)`
  - unica por `(player_id, team_id, season, kind)`;
  - `first_seen_at <= last_seen_at`;
  - observar otra aparicion solo amplia el intervalo;
  - `source` es `fixture`;
  - `kind` debe coincidir con `Competition.participant_kind` de la aparicion que la respalda.

- `PlayerFixtureAppearance(player_id, fixture_id, team_id, season)`
  - identidad compuesta `(player_id, fixture_id)`;
  - `team_id` pertenece al fixture;
  - el snapshot no cambia salvo correccion auditada;
  - se persiste extendiendo `player_stats`, no en una tabla adicional.

### Value objects

- `AffiliationKind(value)` acepta solo `club` o `national_team` y es inmutable.

### Coordinacion de dominio

`IngestCompetitionUseCase` valida el lado del fixture y la coherencia de
`participant_kind`, persiste la aparicion y observa/extiende la afiliacion dentro de una
misma transaccion. No se introduce un aggregate artificial.

### Ubicacion propuesta

- `src/sfa/domain/participation/entities.py`
- `src/sfa/domain/participation/value_objects.py`
- `src/sfa/domain/participation_ports.py`
- `src/sfa/domain/ingestion_ports.py`

## Modelo de persistencia

### `competitions`

- agregar `participant_kind NOT NULL DEFAULT 'club'`;
- check `participant_kind IN ('club', 'national_team')`.

### `player_team_affiliations`

- `id`;
- `player_id` FK;
- `team_id` FK;
- `season`;
- `kind`;
- `first_seen_at`;
- `last_seen_at`;
- `source` con check `source = 'fixture'`;
- timestamps;
- `UNIQUE(player_id, team_id, season, kind)`;
- indices `(player_id, season)` y `(team_id, season)`.

### Snapshots

- `player_stats.team_id` FK, inicialmente nullable y finalmente `NOT NULL`;
- `player_events.team_id` FK, inicialmente nullable y finalmente `NOT NULL`;
- indices `(team_id, season)` y `(team_id, fixture_id)`;
- la aplicacion y la auditoria verifican pertenencia al fixture;
- la auditoria critica verifica igualdad evento-aparicion;
- no se duplica `team_id` en `player_event_scores`.

Una FK cruzada evento-stats no se agrega porque requeriria una clave compuesta adicional y
acoplaria tablas con ciclos operativos. La consistencia se protege en la transaccion de
ingestion, tests de repositorio y auditoria bloqueante.

## Migraciones y backfill

La ultima migracion existente verificada al redactar este spec es
`0020_add_team_id_to_sfa_season_scores.sql`. Se reservan:

- `0021_player_team_affiliations_expand_and_backfill.sql`;
- `0022_player_team_affiliations_constraints.sql`.

Antes de implementarlas se vuelve a listar `migrations/`; si aparecio otra migracion, ambos
numeros se desplazan manteniendo el orden.

### Diagnostico previo

`scripts/audit_player_team_snapshots.sql` debe poder ejecutarse antes de expand sin depender
de columnas nuevas. Simula candidatos, produce conteos y lista IDs unresolved. Su resultado
se adjunta al registro operativo del rollout.

### 0021 - Expand y backfill

1. agregar `competitions.participant_kind` con default `club`;
2. crear `player_team_affiliations`;
3. agregar snapshots nullable;
4. resolver `player_stats.team_id`:
   - primero `sfa_season_scores.team_id` del mismo alcance si pertenece al fixture;
   - despues `players.team_id` solo si pertenece al fixture;
   - conflictos validos se registran y gana el snapshot de score;
   - sin candidato unico, la fila queda unresolved;
5. copiar eventos desde la aparicion exacta;
6. crear afiliaciones desde apariciones;
7. reparar `sfa_season_scores.team_id` con la regla P1 dentro de su competicion;
8. ejecutar auditoria post-backfill;
9. no imponer `NOT NULL`.

El backfill debe ser idempotente y ejecutable por lotes con checkpoints. No se exige una
transaccion unica de larga duracion.

### 0022 - Constraints

Solo se ejecuta con reporte critico en cero:

1. FKs, checks e indices definitivos;
2. `NOT NULL` en snapshots;
3. `players.team_id` nullable y comentario de deprecacion.

## Dual-read y cutover

### Expand

Las escrituras nuevas siempre incluyen snapshot. Las lecturas historicas usan temporalmente:

1. `player_stats.team_id`;
2. si es NULL, `players.team_id` solamente cuando coincide con home o away;
3. si tampoco es valido, resultado no resuelto y telemetria; nunca se inventa un lado.

Para eventos: `player_events.team_id`, luego `player_stats.team_id`, y solo entonces el
fallback legacy validado contra el fixture. Este dual-read se encapsula en resolvers de
infraestructura y no se expande por routers o use cases.

### Cutover

Despues del backfill, ELO rebuild y auditoria en cero:

- eliminar todo fallback a `players.team_id`;
- hacer que un NULL sea error de integridad;
- ejecutar busqueda automatizada de referencias;
- desplegar el binario sin dual-read;
- aplicar `0022`.

La eliminacion del dual-read es un item verificable, no deuda posterior.

## Regla de perfil sin contexto

1. con competicion y temporada: equipo representativo de ese scope por P1;
2. con temporada pero sin competicion: equipo con mas minutos en esa temporada por P1;
3. sin temporada: temporada con aparicion mas reciente y regla P1;
4. sin apariciones: devolver `team_name=null` y `team_logo_url=null`.

No se usa una afiliacion nacional como fallback generico ni se inventa un club. Una
afiliacion sin apariciones no controla presentacion en este spec.

## Infraestructura de tests

No se encontro un `tests/conftest.py` ni fixtures de `AsyncSession` para repositorios en la
revision del codebase. Antes de crear tests de repositorio se debe:

- verificar nuevamente si existe infraestructura equivalente;
- si no existe, crear soporte de integracion contra PostgreSQL 16, preferentemente usando
  el servicio `db` de `docker-compose-development.yml`;
- separar tests unitarios con fakes de tests de integracion SQL;
- no sustituir PostgreSQL por SQLite para queries, constraints o `ON CONFLICT`.

## Compatibilidad y rollout

1. diagnostico previo sobre copia actual;
2. expand con `0021`;
3. despliegue con escrituras nuevas y dual-read;
4. backfill por lotes y correccion de unresolved;
5. auditoria critica en cero;
6. rebuild ELO completo desde baseline reproducible;
7. recalculo de scoring que consume M1 y comparacion;
8. cutover sin dual-read;
9. constraints con `0022`;
10. observacion y reingesta controlada;
11. gate del Mundial;
12. eliminacion fisica posterior de `players.team_id`.

## Integraciones externas

API-Football sigue siendo fuente de identidad y apariciones. No se consulta durante el
backfill. ClubElo se usa solamente para construir el baseline reproducible de clubes en el
rebuild ELO, mediante el flujo existente y una fecha registrada. Las filas ambiguas se
corrigen por reingesta controlada o proceso explicito, nunca con heuristicas automaticas.
