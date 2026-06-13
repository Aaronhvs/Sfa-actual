# 0025 - Historico de jugador, recorridos por competicion y detalle de puntos

## Contexto de negocio

La pagina de jugador permite seleccionar una temporada concreta o `Total historico`, pero
el alcance historico no es consistente en todas sus secciones:

- El detalle principal suma partidos, goles, asistencias y SFA pts de todas las temporadas.
- Los endpoints de eventos y fixtures reciben literalmente `season=all`; el repositorio lo
  interpreta como una temporada almacenada y devuelve una lista vacia.
- Las estadisticas tecnicas se agregan en frontend solo para la competicion principal del
  jugador, por lo que omiten otras competiciones de la misma temporada y del historico.
- Los logros y fases alcanzadas ya existen en `competition_achievements` y
  `player_achievement_bonuses`, pero no hay un endpoint de lectura orientado al perfil.
- El endpoint de fixtures ya entrega un breakdown por tipo de accion y puntos calculado con
  la version activa de scoring. Ese contrato permite explicar el total del partido sin
  recalcular ni modificar el algoritmo.

La feature debe hacer que el selector represente el mismo alcance en toda la pagina, mostrar
el recorrido del jugador por competicion y explicar los puntos de cada partido.

## Restricciones

- No se modifica `SFAScoringService`, `BASE_POINTS_TABLE`, multiplicadores, configuracion de
  reglas, tareas de recalculo ni persistencia de scores.
- No se crean ni modifican tablas. Se reutilizan `player_stats`, `fixtures`,
  `sfa_season_scores`, `competition_achievements`, `player_achievement_bonuses`,
  `player_events` y `player_event_scores`.
- `season=all` es un valor de API, no un valor persistido. Debe normalizarse a ausencia de
  filtro de temporada antes de consultar DB.
- La fuente autoritativa para asociar un jugador con un logro es
  `player_achievement_bonuses`: contiene `player_id`, `team_id`, `competition_id`, `season`
  y `achievement_id`. Esto evita atribuir al jugador actual logros de un equipo historico
  usando `players.team_id`.
- Un mismo logro puede tener bonus para varias versiones de reglas. La lectura de recorridos
  debe resolver una unica version de reglas antes de consultar, para no mezclar ni escoger
  arbitrariamente valores de `final_bonus`.
- Los puntos expuestos para un logro son el valor persistido en
  `player_achievement_bonuses.final_bonus` para ese jugador, logro y version de reglas. No se
  derivan desde `competition_achievements.bonus_points`, no se leen desde
  `calculation_details` y no se recalculan durante la consulta.
- Solo pueden mostrarse recorridos que hayan sido registrados en
  `competition_achievements` y vinculados al jugador mediante el calculo de bonuses. La
  feature no infiere fases desde fixtures ni incorpora una fuente externa.
- `phase` permanece como clave estable de backend (`winner`, `champion`, `runner_up`,
  `semi_final`, `quarter_final`, etc.). La traduccion y presentacion visual pertenecen al
  frontend.
- La cantidad de trofeos se deriva en lectura: `title_count = 1` para `winner` o `champion`,
  y `0` para fases no campeonas. No se persiste un contador nuevo.
- El breakdown de fixtures usa la version activa de scoring, igual que `sfa_pts`. La suma de
  sus entradas debe explicar el total mostrado dentro de la tolerancia de redondeo.
- El frontend actual referencia `formatAction` en `PerformanceChart.tsx` sin definirlo ni
  importarlo. La implementacion debe corregir ese defecto al presentar el breakdown.
- Hay cambios locales existentes en backend y frontend. La implementacion debe trabajar
  sobre ellos y no revertir archivos ajenos a este spec.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Mantener `GET /players/{id}/stats` y hacer `competition_id` opcional | Crear un endpoint historico separado | Conserva compatibilidad y permite que el mismo recurso agregue todas las competiciones del alcance seleccionado. |
| Aceptar `season=all` en stats, fixtures y events como ausencia de filtro de temporada | Consultar por una temporada literal `all` | `all` es una opcion de UI/API y no existe en DB. |
| Las estadisticas del perfil se solicitan sin `competition_id`; si se envia, el filtro existente se conserva | Hacer una llamada por temporada y competicion y sumar en React | Una unica agregacion SQL evita omisiones, round-trips y formulas duplicadas en frontend. |
| Calcular promedios y ratios desde los agregados en el repositorio | Promediar promedios de cada temporada en frontend | `passes_accuracy_avg` debe ponderarse por volumen de pases; los ratios deben usar numerador y denominador globales. |
| Crear `GET /players/{id}/achievements?season=<season|all>` | Incluir recorridos dentro de `PlayerDetailSchema` | Mantiene el detalle principal pequeno y permite cargar/evolucionar la seccion de recorridos de forma independiente. |
| Extender `CompetitionAchievementRepositoryPort` con una lectura por jugador | Crear un segundo repositorio sobre las mismas tablas | Es la extension minima del adapter que ya posee los datos y evita duplicar acceso a persistencia. |
| Relacionar logro y jugador mediante `player_achievement_bonuses` y filtrar una version de reglas | Relacionar por `players.team_id` o solo por `sfa_season_scores.team_id` | El bonus conserva la relacion historica exacta jugador-equipo-logro, su valor real por version y evita atribuciones por el equipo actual. |
| Exponer DTO neutral con competicion, temporada, equipo, fase, `title_count` y `bonus_pts` | Enviar HTML, iconos o etiquetas traducidas desde backend | El backend entrega semantica estable y el bonus real persistido; iconografia, formato y copy son responsabilidad de presentacion. |
| Resolver `rules_version_id` en el use case, usando la version activa como default | Consultar todas las versiones y deduplicar con `DISTINCT`, `MAX`, la mas reciente o una suma | `final_bonus` puede variar entre versiones. Solo un filtro explicito garantiza que el valor coincida con la puntuacion que ve el usuario. |
| Leer `bonus_pts` directamente de `PlayerAchievementBonusModel.final_bonus` | Reaplicar la formula desde `bonus_points`, `weight`, participacion o factores de rendimiento | `final_bonus` es el resultado autoritativo ya calculado y auditado; esta ampliacion es exclusivamente de lectura. |
| Aceptar `rules_version_id` opcional en `GET /players/{id}/achievements` | Ocultar por completo la version elegida dentro del repositorio | Mantiene paridad con el detalle del jugador, permite consultas reproducibles y conserva la version activa como comportamiento por defecto. |
| Reutilizar `PlayerFixtureDTO.breakdown` para el detalle de la linea de tiempo | Exponer `calculation_details` completos o recalcular puntos | El breakdown activo ya agrupa accion, cantidad y puntos y explica el total sin ampliar el algoritmo ni filtrar detalles internos. |
| Mantener hover/focus y permitir click para fijar el tooltip | Tooltip solo por hover | Click y teclado hacen el detalle util en touch y accesible. |
| No invocar DDD Designer | Modelar un agregado nuevo de palmares | Son DTOs de lectura y filtros sobre datos existentes, sin invariantes nuevas ni cambios al dominio de scoring. |

## Domain Model

No se crean entidades, value objects ni aggregates nuevos.

### DTO de lectura nuevo

`PlayerCompetitionAchievementDTO`, ubicado en `src/sfa/domain/scoring_ports.py`:

- `achievement_id: int`
- `competition_id: int`
- `competition_name: str`
- `team_id: int`
- `team_name: str`
- `season: str`
- `phase: str`
- `title_count: int`
- `bonus_pts: float`

`title_count` vale `1` cuando `phase` es `winner` o `champion`; en cualquier otra fase vale
`0`. `bonus_pts` es exactamente el `final_bonus` persistido para el jugador y la version de
reglas resuelta, serializado como numero decimal sin recomputacion. La respuesta se ordena
por temporada descendente y nombre de competicion ascendente.

### Extension de ports existentes

`CompetitionAchievementRepositoryPort` incorpora:

- `get_player_achievements(player_id, season=None, rules_version_id=...) -> list[PlayerCompetitionAchievementDTO]`

`rules_version_id` es obligatorio en la llamada al port de repositorio: la capa de
aplicacion debe resolverlo antes de acceder a persistencia. El
`GetPlayerAchievementsUseCase` recibe un `default_rules_version_id` en construccion y
permite un override explicito en `execute`, siguiendo el patron ya usado por
`GetPlayerDetailUseCase`.

`PlayerEventRepositoryProtocol.get_player_season_stats` cambia su contrato a:

- `competition_id: int | None`
- `season: str | None`

`None` en cualquiera de esos filtros significa agregar todas las competiciones o todas las
temporadas, respectivamente.

## Contratos HTTP

### Estadisticas agregadas

`GET /api/v1/players/{player_id}/stats`

- `season` sigue siendo obligatorio como query param de producto y acepta una temporada o
  `all`.
- `competition_id` pasa a ser opcional.
- Con `season=all` se agregan todas las temporadas.
- Sin `competition_id` se agregan todas las competiciones.
- Se conserva `404` cuando no existen filas de `player_stats` para el alcance.
- El schema de respuesta no cambia. En una respuesta agregada, `competition_id` no puede
  representar una unica competicion y debe pasar a `int | None`; `season` devuelve `all`
  cuando se solicito el historico.

### Recorridos y logros

`GET /api/v1/players/{player_id}/achievements?season=<season|all>&rules_version_id=<id>`

Respuesta: lista de elementos con los campos del DTO de lectura. `season` omitida resuelve
la temporada mas reciente disponible para el jugador; `season=all` omite el filtro.
`rules_version_id` es opcional en HTTP; si se omite, el use case utiliza la version activa
inyectada por `core/dependencies.py`. Una lista vacia responde `200`, porque significa que
no hay recorridos registrados o bonuses persistidos para el alcance y version solicitados.

El contrato agrega:

- `bonus_pts: float`: valor de `player_achievement_bonuses.final_bonus` del registro que
  coincide con `player_id`, `achievement_id` y la version de reglas resuelta.

El endpoint no suma bonuses entre logros, temporadas o versiones. Cada elemento informa el
bonus individual que corresponde a ese recorrido. Tampoco expone `calculation_details`.

### Eventos y fixtures

Los contratos existentes no cambian. Los use cases normalizan `season=all` a `None` antes
de llamar al repositorio. `GET /players/{id}/fixtures` mantiene `include_breakdown=true`
por defecto.

## Limites de responsabilidad frontend

- Hacer una sola llamada de stats por alcance seleccionado, sin agregar temporadas ni
  competiciones en React.
- Cargar recorridos para el mismo `season` seleccionado.
- Solicitar recorridos con la misma `rules_version_id` usada por el detalle y ranking.
- Traducir `phase` a copy en espanol y elegir icono: trofeo para `title_count=1`; nombre de
  fase para eliminaciones o subcampeonatos.
- Mostrar `bonus_pts` como puntos SFA obtenidos junto al trofeo o resultado, sin recalcularlo
  ni inferirlo desde `title_count`.
- Agrupar visualmente recorridos por temporada cuando `season=all`.
- Insertar la seccion entre Estadisticas tecnicas y Rendimiento por partido.
- Mostrar en el tooltip de cada partido cada entrada del breakdown con etiqueta, cantidad
  y puntos; permitir hover, focus y click para fijarlo.
- Definir o importar `formatAction` y contemplar claves desconocidas con fallback legible.

## Integraciones externas

Ninguna. La feature solo lee datos ya persistidos por los flujos existentes de ingestion,
scoring y registro/calculo de logros.
