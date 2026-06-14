# Contexto de goles por transición y calibración versionada de M3/M4

## Contexto de negocio

SFA puntúa goles y asistencias según el contexto existente en el momento de la acción. El
fixture API-Football `1489370` terminó USA 4-1 Paraguay. Mauricio marcó para Paraguay al 73',
cuando el marcador previo real era 3-0. Sin embargo, `player_events` guardó minuto 73,
`score_before=2:1` y `score_diff=-1`.

La causa factual está confirmada:

- API-Football devuelve el autogol de D. Bobadilla al 7' con `team.id=2384` (USA), es decir,
  el equipo beneficiado por el gol.
- `APIFootballProvider.get_score_at_minute()` y
  `ReingestPlayerUseCase._get_score_at_minute()` vuelven a invertir el equipo de los autogoles.
- `ReingestPlayerUseCase` entrega a esa reconstrucción `home_team_id` interno de la DB, mientras
  los eventos contienen `team_external_id` de API-Football.
- Los dos errores reconstruyen artificialmente 2-1 antes del gol de Mauricio.

También hay dos problemas de calibración:

- `M3MinuteScore` asigna 1.6 a cualquier `score_diff < 0` entre 70' y 79'. No distingue un
  empate inminente (`-1 -> 0`) de reducir una goleada (`-3 -> -2`).
- `IngestCompetitionUseCase` y `ReingestPlayerUseCase` guardan `psxg=0.32` cuando no existe
  PSxG real. Eso produce M4=1.5 en la configuración actual, aunque el contrato del dominio
  establece que PSxG ausente debe producir M4=1.0.

La solución debe corregir los hechos crudos y crear una regla de trascendencia que mida la
transición causada por el gol con la información disponible en ese instante. No se utilizará
el resultado final para penalizar o premiar retroactivamente una acción: un gol que puso 1-0
seguirá siendo trascendente aunque el partido termine 5-0.

## Restricciones

- Arquitectura hexagonal estricta: Provider/Repository -> Use Case -> Domain. La lógica de
  reconstrucción del marcador no puede quedar duplicada en provider y use case.
- `player_events` representa hechos crudos compartidos por todas las versiones. Las reglas
  antiguas y sus filas en `player_event_scores` deben continuar siendo reproducibles.
- No se activará una nueva versión ni se alterará el ranking visible durante la reparación.
- API-Football usa IDs externos; los IDs internos de `teams.id` no pueden entrar en el
  algoritmo de reconstrucción.
- El orden por minuto no basta: puede haber varios eventos en el mismo minuto. Debe conservarse
  el orden de la respuesta del proveedor mediante una secuencia estable.
- Los autogoles participan en la línea de marcador, pero no crean un evento puntuable GOAL para
  el jugador que los cometió.
- Los goles de tanda no modifican el marcador reglamentario usado por M3.
- Ningún valor sintético (`0.32`, `0.75`, promedio por temporada o xG) puede etiquetarse como
  PSxG real. Si no hay PSxG real por disparo, M4 es exactamente 1.0.
- La reparación histórica debe ser idempotente, reanudable por scope y auditable antes de
  activar la nueva versión.
- El alcance histórico comprende todas las temporadas y competiciones con eventos
  GOAL/GOAL_PENALTY/ASSIST/CORNER_ASSIST, no solo el Mundial 2026.
- No se requiere acceso a producción durante la implementación. La activación sí exige ejecutar
  auditorías y gates sobre una copia reciente y luego sobre producción.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Crear un servicio puro de dominio `ScoreTimeline` como única fuente para reconstruir el marcador | Mantener helpers separados en provider y reingesta | La duplicación produjo el bug y permite divergencias futuras. |
| Interpretar `FixtureEventRawDTO.team_external_id` como equipo beneficiado por el gol, incluso en `Own Goal` | Invertir el equipo para autogoles | Es la semántica observada y validada de API-Football para el fixture 1489370. |
| Agregar `source_sequence` al DTO raw y ordenar por `(minute, extra_minute, source_sequence)` | Ordenar solo por minuto | Dos eventos pueden compartir minuto; M3 necesita el estado inmediatamente anterior al evento exacto. |
| Mantener exclusivamente IDs externos dentro de `ScoreTimeline` | Aceptar indistintamente IDs internos y externos | Mezclar namespaces produce resultados válidos en tipo pero incorrectos en negocio. |
| Persistir `score_before`, `score_after`, `score_diff` y `score_diff_after` | Inferir siempre `after = before + 1` al leer | La transición persistida es auditable, permite invariantes SQL y detecta corrupción de datos. |
| Añadir `source_event_key` estable por fixture/evento | Identificar eventos solo por jugador, tipo y minuto | Permite asociar scorer y assist al mismo gol, reparar en sitio y manejar eventos del mismo minuto. |
| Reemplazar la M3 nueva por una función de transición `before -> after` y banda de minuto | Añadir el resultado final como multiplicador | La transición mide impacto causal sin hindsight. |
| Versionar la tabla de factores M3 dentro de `ScoringConfig` | Cambiar los valores hardcodeados globalmente | Las reglas antiguas deben permanecer reproducibles y comparables. |
| Config ausente usa el algoritmo legacy; config nueva usa transición | Migrar automáticamente todas las versiones existentes | Mantiene compatibilidad exacta con versiones ya creadas. |
| Evento con contexto irresuelto no se calcula en la nueva versión y queda reportado | Usar `score_diff=0` como fallback | El fallback actual convierte datos desconocidos en una bonificación de empate y oculta corrupción. |
| PSxG ausente se guarda como NULL y M4=1.0 | Persistir `0.32` como supuesto neutral | En la fórmula actual 0.32 no es neutral; genera M4 alto. |
| Añadir procedencia de dificultad de disparo | Tratar cualquier número en `psxg` como real | Los proxies históricos no son PSxG real por disparo y no deben recibir bonus M4. |
| Reparar eventos existentes en sitio conservando `player_events.id` cuando el match sea inequívoco | Borrar y recrear todos los eventos | Borrar activa `ON DELETE CASCADE` sobre scores históricos y rompe comparaciones entre versiones. |
| Detener y reportar fixtures ambiguos, sin borrado parcial | Elegir el primer match por heurística | Una reparación silenciosamente incorrecta es peor que un fixture pendiente. |
| Crear y calcular una versión nueva en sombra antes de activarla | Recalcular la versión activa | El ranking público no cambia hasta superar invariantes y revisión de distribución. |

## Domain Model

### Bounded context

**Scoring subdomain.** La línea de marcador es un hecho futbolístico usado directamente para
calcular la trascendencia de una acción. No necesita un bounded context nuevo ni un aggregate
persistente independiente.

### Nuevas entidades

No se agregan entidades de dominio con identidad propia. La identidad persistente continúa
siendo `PlayerEvent`; la línea temporal y sus transiciones son valores derivados e inmutables.

### Nuevos value objects

- `ScoreState(home_goals, away_goals)`
  - Invariantes: ambos enteros y `>= 0`.
  - Operación: diferencia desde la perspectiva de un `team_external_id` validado contra los
    equipos del fixture.

- `GoalTimelineEvent(source_event_key, source_sequence, minute, scoring_team_external_id,
  detail, is_shootout)`
  - Invariantes: `source_sequence >= 0`, minuto total `>= 0`, y el equipo beneficiado debe ser
    exactamente home o away.
  - `Own Goal` conserva `scoring_team_external_id` entregado por API-Football; no se invierte.

- `ScoreTransition(before, after, scoring_team_external_id, source_event_key)`
  - Invariantes: para un gol reglamentario `after` incrementa exactamente en uno al equipo
    beneficiado y deja sin cambios al rival.
  - La diferencia del equipo beneficiado siempre cumple `diff_after = diff_before + 1`.

- `GoalImpactClass`
  - `FAR_DEFICIT_REDUCTION`: `diff_before <= -3`
  - `REACHABLE_DEFICIT_REDUCTION`: `diff_before == -2`
  - `EQUALIZER`: `diff_before == -1`
  - `GO_AHEAD`: `diff_before == 0`
  - `INSURANCE`: `diff_before == 1`
  - `RUNAWAY_EXTENSION`: `diff_before >= 2`

- `M3GoalTransition(minute, transition, is_penalty, is_shootout, config) -> value`
  - Es inmutable y no consulta resultado final.
  - `is_shootout=True`: factor configurado `1.5`.
  - `is_penalty=True`: factor configurado `0.6`, conservando el comportamiento actual.
  - Para goles/asistencias reglamentarios usa `GoalImpactClass` y banda de minuto.
  - Rango válido configurable y validado: `(0, 3.0]`.

- `ShotDifficultyEvidence(value, source)`
  - `source`: `actual_psxg`, `estimated`, `missing`, `legacy_unknown`.
  - Solo `actual_psxg` puede alimentar `M4ShotDifficulty`.
  - `estimated`, `missing` y `legacy_unknown` producen M4=1.0.

### Aggregates modificados o nuevos

- `ScoringConfig`
  - Agrega `m3_transition_factors`, `m3_penalty_factor`, `m3_shootout_factor` y
    `m3_transition_clamp`.
  - Configs antiguas sin esos campos usan `M3MinuteScore` legacy sin alterar resultados.
  - `from_dict()` y `to_dict()` deben preservar round-trip de versiones antiguas y nuevas.

- `PlayerEventScore`
  - No cambia su identidad.
  - `calculation_details` registra clase de impacto, marcador antes/después, diferencias,
    banda de minuto, fuente de PSxG y razón de neutralidad de M4.

### Cambios en ActionType

No se agregan acciones. Los autogoles siguen excluidos de `ActionType.GOAL`; solo alimentan
`ScoreTimeline`.

### Cambios en BASE_POINTS_TABLE

No aplica. Este refactor cambia contexto y multiplicadores, no puntos base.

### Tabla inicial de M3 para la nueva versión

Los valores son configuración inicial auditable, no constantes globales:

| Clase de transición | 1-44 | 45-69 | 70-79 | 80-120 |
|---|---:|---:|---:|---:|
| `FAR_DEFICIT_REDUCTION` (`<= -3 -> +1`) | 0.75 | 0.75 | 0.75 | 0.70 |
| `REACHABLE_DEFICIT_REDUCTION` (`-2 -> -1`) | 0.90 | 0.95 | 1.00 | 1.00 |
| `EQUALIZER` (`-1 -> 0`) | 1.00 | 1.30 | 1.80 | 2.50 |
| `GO_AHEAD` (`0 -> 1`) | 1.00 | 1.20 | 1.50 | 2.20 |
| `INSURANCE` (`1 -> 2`) | 0.90 | 0.95 | 1.05 | 1.15 |
| `RUNAWAY_EXTENSION` (`>= 2 -> +1`) | 0.70 | 0.70 | 0.70 | 0.65 |

Con esta tabla, el gol de Mauricio al 73' con transición `3-0 -> 3-1`, desde la perspectiva de
Paraguay `-3 -> -2`, recibe M3=0.75. No recibe 1.6 ni se consulta el 4-1 final.

### Ubicación propuesta

- `domain/scoring/value_objects.py` — `ScoreState`, `ScoreTransition`, `GoalImpactClass`,
  `M3GoalTransition`, `ShotDifficultyEvidence` y extensión de `ScoringConfig`.
- `domain/scoring/services.py` — `ScoreTimeline`, servicio puro que produce transiciones.
- `domain/ingestion_ports.py` — secuencia, clave de fuente y semántica explícita de IDs externos.
- `domain/scoring_ports.py` — contexto antes/después y procedencia de PSxG para recálculo.

## Modelo de persistencia

Una migración expand-only nueva, posterior a `0022`, agrega a `player_events`:

- `source_event_key VARCHAR(100) NULL`
- `source_sequence INTEGER NULL`
- `score_after VARCHAR(10) NULL`
- `score_diff_after SMALLINT NULL`
- `context_status VARCHAR(30) NOT NULL DEFAULT 'legacy_unverified'`
- `shot_difficulty_source VARCHAR(30) NOT NULL DEFAULT 'legacy_unknown'`

Índices:

- índice parcial por `(fixture_id, source_event_key)` donde `source_event_key IS NOT NULL`
- índice por `(context_status, fixture_id)` para auditoría y reanudación

No se agrega aún `NOT NULL` a los campos de transición: los eventos STATS no los usan y la
reparación histórica puede encontrar fixtures ambiguos. La aplicación impone que una nueva
versión de transición solo puntúe eventos individuales con `context_status='verified'`.

## Integraciones externas

### API-Football v3

- `GET /fixtures/events?fixture={external_id}` es la fuente autoritativa para orden, minuto,
  detalle y equipo beneficiado.
- El adapter asigna `source_sequence` según el índice de la respuesta original.
- `source_event_key` se deriva de fixture externo, secuencia, minuto, tipo, detalle y equipo
  beneficiado. Debe ser determinista y estable para la misma respuesta.
- La respuesta no aporta PSxG real por disparo. Por tanto, ingesta y reingesta guardan
  `psxg=NULL`, `shot_difficulty_source='missing'`.
- Si API-Football cambia el orden o contenido histórico, el dry-run reporta diferencias antes
  de escribir.

## Estrategia de reparación y activación

1. Desplegar migración expand y código compatible, sin modificar la versión activa.
2. Ejecutar dry-run sobre fixture `1489370`; gate esperado:
   - secuencia reglamentaria `USA 1-0` al 7', `2-0`, `3-0`, `3-1` al 73', `4-1`;
   - Mauricio: `score_before=3:0`, `score_after=3:1`, `score_diff=-3`,
     `score_diff_after=-2`;
   - PSxG ausente y M4 neutral.
3. Auditar todos los fixtures históricos por lotes. Comparar marcador reconstruido con
   `FixtureRawDTO.home_goals/away_goals`; no escribir fixtures que no cierren.
4. Reparar en sitio los eventos inequívocos y marcar `context_status='verified'`.
5. Reingestar solo fixtures ambiguos o sin correspondencia; preservar IDs cuando exista match
   inequívoco. Los pendientes quedan `unresolved`, visibles en el reporte.
6. Crear una nueva `ScoringRulesVersion` inactiva con tabla M3 de transición.
7. Recalcular en sombra por temporada/competición con `force_recalculate=True`.
8. Comparar distribución, top N, extremos M3/M4 y fixture 1489370.
9. Activar solo con contadores críticos en cero y aprobación explícita.

## Invariantes y gates de rollout

- Cero timelines verificados cuyo marcador final reconstruido difiera del resultado del fixture.
- Cero eventos verificados con equipo beneficiado fuera de home/away.
- Cero transiciones verificadas donde el equipo beneficiado no aumente exactamente un gol.
- Cero scorer/assist del mismo `source_event_key` con contexto distinto.
- Cero eventos nuevos con `psxg IN (0.32, 0.75)` y fuente `missing`.
- Todo evento con `shot_difficulty_source != 'actual_psxg'` produce M4=1.0 en la nueva versión.
- Cero eventos individuales incluidos en la nueva versión con contexto distinto de `verified`.
- La versión activa previa, sus `player_event_scores` y sus `sfa_season_scores` no cambian
  durante reparación y shadow recalculation.
- El conteo y total de scores de versiones antiguas permanece idéntico antes/después del rollout.

## Rollback

- Antes de reparar, exportar las filas afectadas de `player_events` y los contadores/totales por
  versión.
- La migración es expand-only y no requiere rollback destructivo inmediato.
- Si una reparación falla, detener el lote; las filas ya verificadas son idempotentes y las
  restantes continúan `legacy_unverified` o `unresolved`.
- No activar la nueva versión si existe cualquier unresolved crítico.
- Si la versión nueva ya fue calculada pero no activada, eliminar únicamente sus
  `player_event_scores` y `sfa_season_scores`.
- Si fue activada y se detecta regresión, reactivar la versión anterior en una transacción. No
  borrar hechos reparados que hayan superado invariantes.

