# Temporada de premio compuesta con Mundial 2026

## Contexto de negocio

El Mundial 2026 termino y SFA debe volver a presentar como pagina principal el premio de la
temporada de clubes 2025/2026. Ese premio no puede ignorar el torneo internacional disputado al
final del ciclo: los puntos y bonos obtenidos por cada jugador en el Mundial deben sumarse a los
de sus clubes para determinar al mejor jugador de la temporada.

Al mismo tiempo, el Mundial debe conservarse como una vista seleccionable e independiente. El
selector debe poder representar sin colisiones `2024/2025`, `2025/2026`, `Mundial 2026` y, cuando
tenga datos, `2026/2027`. Esto no puede resolverse usando solo el valor fisico `season`, porque
API-Football almacena clubes 2025/2026 como `2025`, el Mundial como `2026` y clubes 2026/2027
tambien como `2026`.

La version mas reciente del motor se termino de calibrar durante el Mundial. La temporada regular
2025 debe recalcularse con exactamente el mismo snapshot de reglas que el Mundial antes de sumar
ambos componentes. El ELO del Mundial ya esta preparado y no se vuelve a sembrar ni progresar en
esta feature. El ELO de clubes, en cambio, debe normalizar su ciclo operativo antes del recalculo:
hoy parte del rating mutable, procesa solo la competicion recien ingerida y encola scoring en
paralelo, por lo que una reingesta puede producir resultados distintos o usar strengths viejas.

## Restricciones

- La base conserva temporadas fisicas: clubes `2025` y Mundial `2026`; no se reescriben fixtures,
  eventos, estadisticas ni temporadas para fabricar una temporada sintetica.
- `players.external_id` es unico y la ingesta hace upsert por ese identificador. La identidad del
  jugador ya permite unir club y seleccion por `player_id`; no se crea una tabla de equivalencias.
- `player_event_scores` y `sfa_season_scores` siguen siendo las fuentes de verdad versionadas.
- Los puntos del Mundial se cuentan una sola vez. Una vista compuesta agrega fuentes existentes,
  pero nunca copia scores a otra season.
- `sfa_total_pts = total_pts + achievement_bonus_pts` es el total que determina el premio. Los
  logros del club y del Mundial se incluyen con su version de reglas correspondiente.
- Todos los componentes de una temporada de premio deben usar el mismo `rules_version_id`. Si no
  existe una version comun completa, la consulta falla de forma explicita; nunca mezcla motores.
- La logica comun del motor se reutiliza. Las reglas genuinamente especificas del Mundial se
  mantienen condicionadas por competicion: sede neutral, ELO de selecciones, fases y bonuses.
- Clubes y selecciones son pools ELO separados: sus ratings absolutos no se comparan entre si.
  Ambos comparten formula, normalizacion y ciclo determinista, y M1 solo compara equipos del
  mismo pool dentro de un fixture.
- Todo ELO progresivo se reconstruye desde `elo_seed_raw` y fixtures finalizados. Nunca se usa el
  `elo_raw` vigente como baseline para volver a reproducir el historial.
- El pool de clubes procesa todas las competiciones activas de la season en una sola cronologia.
  Un recalculo de liga aislado no puede replicar un rating parcial sobre copas europeas o locales.
- Una fila ELO no puede ser sobrescrita por el calculo standings-based. Los equipos sin seed deben
  tener un baseline explicito y auditable antes de participar en el replay.
- El resultado del fixture para ELO debe provenir de marcador final oficial y estado terminado;
  mientras el modelo no persista marcador oficial completo, el adapter valida status final y
  cobertura de stats y falla/excluye de forma visible en vez de asumir un empate 0-0.
- La temporada principal se deriva de la temporada de clubes mas reciente con scores, no del
  maximo string de `SFASeasonScore.season`. Mientras no existan scores de clubes 2026, la principal
  es `2025/2026` aunque existan scores fisicos `2026` del Mundial.
- La API existente con `season=` sigue funcionando como alcance fisico durante la transicion. El
  nuevo parametro canonico `scope=` representa opciones de producto y evita la colision de 2026.
- Arquitectura hexagonal estricta: Router -> Use Case -> Repository. Los routers no resuelven ni
  construyen scopes y los repositories retornan DTOs de dominio, no modelos ORM.
- No se agrega una tabla de periodos ni una migracion de persistencia. El catalogo se deriva de
  fixtures, competiciones y scores existentes con una politica de inclusion explicita.
- El entorno local actual no dispone de Docker; las verificaciones con PostgreSQL y el recalculo
  real deben ejecutarse en un entorno Docker/VPS antes de activar la nueva version.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Introducir un `AwardPeriodScope` de dominio compuesto por fuentes fisicas | Cambiar el Mundial de `season=2026` a `season=2025` | Conserva hechos de origen, auditoria e integridad de ingesta. |
| Usar claves canonicas `season-2024`, `season-2025` y `world-cup-2026` | Usar solo `2024`, `2025`, `2026` | `2026` ya tiene dos significados de producto: Mundial y futura temporada de clubes. |
| Extender endpoints de lectura con `scope=` y mantener `season=` como compatibilidad fisica | Cambiar la semantica de `season=2025` silenciosamente | Evita romper consumidores y hace explicita la nueva agregacion. |
| Definir `season-2025` como clubes `2025` mas World Cup `2026` | Crear filas agregadas en `sfa_season_scores` | Las filas sinteticas duplicarian puntos y harian ambiguos logros, breakdown y recalculos. |
| Resolver la temporada principal desde la ultima season con competiciones `participant_kind='club'` | Usar `MAX(season)` global | El Mundial no debe desplazar la portada a una edicion separada. |
| Exigir un unico `rules_version_id` comun en todo scope compuesto | Resolver la version mas nueva por componente | Mezclar configuraciones impide afirmar que el ranking usa una sola logica. |
| Crear un snapshot inmutable de las reglas finales y recalcular clubes y Mundial en sombra antes de activarlo | Reutilizar a ciegas el ID activo | Las migraciones historicas han ajustado config existente; un snapshot nuevo hace reproducible el cierre del premio. |
| Recalcular cada componente mediante los use cases versionados existentes | Copiar al pipeline regular las ramas del Mundial | El motor ya es comun; solo cambian contexto, strengths y configuracion por competicion. |
| No recalcular el ELO nacional durante este rollout | Volver a sembrar/progresar el ELO del Mundial | El usuario confirmo que ese ELO esta listo; los scores nuevos deben leerlo sin modificarlo. |
| Reutilizar `CalculateEloRatingsUseCase` con baseline de seed obligatorio para clubes y selecciones | Mantener el camino mutable `elo_v1` para clubes | Un replay desde seed es idempotente y elimina compounding en reingestas. |
| Resolver todas las competiciones de clubes de la season antes del replay | Procesar solo la competicion recien ingerida | El ELO de club es global por season segun el spec 0017; un subset no representa el rating global. |
| Coordinar ELO de clubes y scoring en una sola task bajo advisory lock | Encolar `apply_elo_update_task` y full recalc por separado | Evita que scoring lea strengths anteriores o parciales. |
| Mantener pools separados con politica K explicita (`club=30`, `national_team=20`) | Forzar un ranking absoluto comun entre ClubElo y World Football Elo | No existen fixtures club-seleccion; se normaliza la semantica operacional y la sensibilidad de M1, no las poblaciones externas. |
| Usar una unica transformacion `strength=clamp((elo-1400)/700*100)` y el mismo divisor M1 del snapshot | Normalizar por min/max observado de cada torneo | Una normalizacion dependiente del conjunto cambia historicamente cuando entran equipos; la transformacion fija es reproducible. |
| Proteger todos los endpoints `/admin/elo/*` con `X-Admin-Key` | Proteger solo los endpoints nacionales | Seed y recalculate de clubes tambien mutan datos de produccion. |
| Para el scope de premio mostrar como equipo representativo un club del componente regular | Mostrar la seleccion si aporto mas puntos | La portada representa la temporada de clubes; el scope Mundial mantiene la seleccion. |
| Aplicar el scope a ranking, perfil, eventos, fixtures, stats, logros y explicaciones | Cambiar solo el ranking | Un total compuesto con detalle parcial seria incoherente y no auditable por el usuario. |
| Mantener `all` como historico fisico sin volver a sumar rollups | Sumar scopes de premio en el historico | Los scopes se solapan con sus fuentes; sumar scopes duplicaria todos los puntos. |
| Publicar `2026/2027` cuando existan scores de clubes 2026 | Crear ahora una opcion activa sin datos | Evita una pantalla vacia presentada como temporada disponible. |

## Domain Model

### Bounded context

**Read model de temporadas y ranking, con referencia al subdomain de scoring.** El scope no cambia
la formula ni crea puntos: define que hechos versionados pertenecen a una vista de producto. La
invariante de una sola version de reglas protege la interpretacion del score.

### Nuevas entidades

No se agregan entidades con identidad persistente ni aggregates ORM.

### Nuevos value objects

- `ScoreSource(season, competition_ids)`
  - Inmutable.
  - `season` no puede estar vacio.
  - `competition_ids` es una tupla no vacia, ordenada y sin duplicados.
  - Una fuente identifica filas fisicas; no contiene labels ni reglas de presentacion.

- `AwardPeriodScope(key, label, kind, sources, is_latest, includes_world_cup)`
  - Inmutable.
  - `key` y `label` no pueden estar vacios.
  - `kind` pertenece a `award_period`, `tournament` o `all_time`.
  - Un scope distinto de `all_time` contiene al menos una fuente.
  - Ningun par `(season, competition_id)` se repite entre fuentes del mismo scope.
  - Un scope `tournament` contiene exactamente una competicion en una fuente.
  - `includes_world_cup=True` exige una fuente de la competicion Mundial.
  - `is_latest=True` solo es valido para un `award_period`, nunca para un torneo separado.

- `ScopeRulesVersion(rules_version_id, covered_sources)`
  - Inmutable.
  - La version es valida solo si cubre todas las fuentes del scope.
  - Cobertura parcial produce un error de dominio `InconsistentScopeRulesVersionError`.

### Aggregates modificados o nuevos

No se modifica `PlayerSeasonScore`. El total compuesto es una proyeccion de lectura por
`player_id`, no un nuevo aggregate de escritura.

### Cambios en ActionType

No aplica. No se agregan acciones ni puntos base.

### Cambios en BASE_POINTS_TABLE

No aplica. La unificacion se consigue usando el mismo `ScoringRulesVersion`, no duplicando tablas
de puntos.

### Ubicacion propuesta

- `domain/season_scope.py`: `ScoreSource`, `AwardPeriodScope`, `ScopeKind` y errores de dominio.
- `domain/ports.py`: extender `SeasonDTO` y los read-side protocols para recibir scopes.
- `domain/scoring_ports.py`: contrato de orquestacion/auditoria por componentes versionados.

## Catalogo de scopes

El `SeasonRepository` construye el catalogo desde datos reales:

1. Cada season con scores de una competicion `participant_kind='club'` crea un scope
   `season-{year}` con label `{year}/{year+1}`.
2. Cada Mundial con scores crea un scope de torneo `world-cup-{year}`.
3. La politica del cierre 2025/2026 agrega al scope `season-2025` la fuente del Mundial 2026.
4. La ultima season de clubes se marca `is_latest=True`; el Mundial nunca recibe esa marca.
5. Cuando aparezcan scores de clubes con season `2026`, se crea `season-2026` con label
   `2026/2027` sin absorber el Mundial 2026.
6. `all` continua siendo una opcion virtual que agrega cada fila fisica una sola vez.

Respuesta esperada de `/api/v1/seasons` durante el cierre:

| key | label | kind | latest | Mundial incluido |
|---|---|---|---:|---:|
| `season-2024` | `2024/2025` | `award_period` | no | no |
| `season-2025` | `2025/2026` | `award_period` | si | si |
| `world-cup-2026` | `Mundial 2026` | `tournament` | no | si |

`season-2026` se agrega como `2026/2027` cuando existan scores de clubes de esa season.

## Contrato HTTP

- `GET /api/v1/seasons` agrega por opcion: `key`, `label`, `kind`, `is_latest`,
  `is_world_cup` e `includes_world_cup`. Conserva `season` durante compatibilidad.
- `GET /api/v1/ranking` acepta `scope`. Sin `scope` ni `season`, resuelve el scope latest.
- Los endpoints de player detail, events, fixtures, stats y achievements aceptan el mismo
  `scope` para que total y desglose compartan fuentes.
- Los endpoints de explicaciones aceptan `scope_key`; el scope persistido para el periodo de
  premio es `award_period` y no reutiliza el texto especial `world_cup`.
- Si llegan `scope` y `season` simultaneamente, el router responde 422 para evitar ambiguedad.
- Las URLs antiguas con solo `season` mantienen la consulta fisica actual. El frontend migra a
  URLs canonicas con `scope` y conserva lectura/redireccion de enlaces antiguos del Mundial.

## Semantica de agregacion

Para `scope=season-2025` y una version comun `R`:

- incluir todas las filas `(season='2025', participant_kind='club', rules_version_id=R)`;
- incluir filas `(season='2026', competition='World Cup', rules_version_id=R)`;
- agrupar por `player_id`;
- sumar `total_pts`, `achievement_bonus_pts`, partidos, goles, asistencias y breakdown;
- ordenar el ranking principal por la suma de ambos campos de puntos;
- aplicar filtros de posicion y perfil despues de construir el conjunto compuesto;
- aplicar `competition_id` como interseccion: al elegir una competicion concreta solo aporta esa
  competicion y no se agrega el Mundial de forma oculta;
- elegir equipo/escudo/competicion representativa desde las fuentes de club para el award period;
- para `world-cup-2026`, limitar todas las lecturas a la unica fuente Mundial.

Los fixtures y eventos se unen por sus IDs fisicos y se ordenan por fecha. Las estadisticas usan
agregacion ponderada existente para precision de pase y suman el resto de contadores. Los logros
se concatenan por sus fuentes sin recrear bonuses.

## Estrategia de recalculo y activacion

1. Auditar la version y configuracion que produjo el cierre del Mundial; no asumir un ID fijo.
2. Crear mediante el flujo versionado existente un snapshot inactivo con la configuracion final
   del motor del Mundial. No mutar `config_json` despues de crearlo.
3. Verificar cobertura de seeds de clubes 2025 y conservar el ELO nacional ya existente para
   Mundial 2026.
4. Reconstruir el ELO de clubes 2025 desde `elo_seed_raw` usando todas sus competiciones y solo
   fixtures finalizados; auditar que dos ejecuciones producen el mismo hash de ratings.
5. Recalcular en sombra todos los componentes de `season-2025` con ese mismo ID, incluyendo
   inferencia de logros y bonuses por competicion.
6. Generar la proyeccion y explicaciones de `scope=season-2025` sin activar la version.
7. Ejecutar gates de conteo, version comun, ausencia de duplicados y reconciliacion de puntos.
8. Activar el snapshot solo cuando todos los gates pasen.
9. La portada cambia a `scope=season-2025` por resolucion de latest, no por un hardcode frontend.

El orquestador de recalculo recibe un `scope_key` y un `rules_version_id`, toma un advisory lock,
resuelve las competiciones fisicas de cada fuente y reutiliza los use cases actuales de scoring,
logros y bonuses. No activa versiones automaticamente. Exige que el ELO de clubes haya superado
su gate determinista; el ELO nacional no se modifica.

## Gates de rollout

- Existe exactamente un `rules_version_id` comun con scores para todas las fuentes del scope.
- El replay ELO de clubes ejecutado dos veces desde el mismo seed produce exactamente los mismos
  ratings y strengths.
- Todas las filas ELO de clubes usadas por M1 tienen `elo_seed_raw`, source progresivo de club y
  cobertura en todas las competiciones activas del equipo.
- Ningun fixture no finalizado participa del replay ELO.
- Cero jugadores duplicados por `external_id` y cero scores sin `player_id` resoluble.
- Para cada jugador del top N: `award_total = club_total + world_cup_total`, incluidos bonuses.
- La suma global del scope es igual a la suma de sus fuentes y no contiene filas sinteticas.
- `world-cup-2026` conserva el mismo total que su fuente fisica aislada.
- `season-2025` es latest mientras no existan scores de clubes 2026.
- Si aparecen scores de clubes 2026, `season-2026` y `world-cup-2026` son opciones distintas.
- Todos los fixtures mostrados en un perfil compuesto pertenecen a una de sus fuentes.
- Las explicaciones del ranking usan evidencia de club y Mundial y el mismo rules version.
- Los filtros por competicion, posicion, perfil y busqueda conservan count, rank y paginacion.
- La API legacy con `season=` conserva sus resultados fisicos previos.

## Rollback

- Como el recalculo es versionado, una version sombra fallida se abandona sin borrar hechos raw.
- Si la version nueva fue activada y falla un gate, reactivar la version anterior; no borrar ELO,
  fixtures, eventos ni estadisticas.
- El frontend puede volver temporalmente a consultas fisicas `season=2025` sin revertir datos.
- No se eliminan scores de la version nueva hasta guardar auditorias y confirmar que no se usaran
  para comparacion.

## Integraciones externas

No se agregan proveedores externos. API-Football ya entrego los hechos de clubes y Mundial; el
provider de ELO nacional no se invoca en este cambio. El despliegue solo usa PostgreSQL, Redis y
Celery existentes.
