# Filtro de Perfil: Goleador y Asistidor en el Ranking

## Contexto de negocio

El filtro "Perfil" del ranking de jugadores hoy solo ofrece "Promesa" y "Veterano" (basados en
cuál bono B1 de edad es mayor). Se agregan dos perfiles nuevos, "Goleador" y "Asistidor", que
permiten filtrar jugadores por un umbral simple de producción ofensiva dentro del scope
filtrado (temporada/competición/posición actuales): al menos 1 gol o al menos 1 asistencia
respectivamente.

A diferencia de Promesa/Veterano — que son mutuamente excluyentes porque se derivan de cuál
bono B1 es mayor — Goleador y Asistidor no son mutuamente excluyentes entre sí: un jugador
puede cumplir ambos criterios a la vez. Esto no genera conflicto en la UI porque el selector de
"Perfil" es de un solo valor por request.

El filtro debe aplicarse en SQL (server-side), no en el cliente: el ranking usa paginación
server-side (15 jugadores por página, `total`/`total_pages` calculados por el backend). Si el
filtro se aplicara solo sobre los jugadores ya paginados, los conteos quedarían mal y
aparecerían páginas vacías con jugadores que sí cumplen el filtro pero están en otras páginas.

## Restricciones

- Los campos `goals` y `assists` ya se calculan en `sfa_score_repository.py` a partir del JSON
  `breakdown` de `SFASeasonScore` (`goal` + `goal_penalty` para goals, `assist` +
  `corner_assist` para assists) y ya viajan en `RankedPlayerDTO` / `RankedPlayerSchema`. No se
  necesita ningún dato nuevo.
- El endpoint `/ranking` ya expone un query param `bonus_label` usado por 4 métodos del
  repository (`get_ranking`, `get_ranking_total`, `get_ranking_all_seasons`,
  `get_ranking_total_all_seasons`). El filtro nuevo debe convivir con ese mismo mecanismo de
  paginación/conteo sin romper los 4 métodos.
- `get_ranking_total` y `get_ranking_total_all_seasons` no agregan `goals`/`assists` hoy — solo
  agregan B1 (edad) cuando `bonus_label` no es `None`. Hay que agregar la sumatoria de
  goals/assists en esos dos métodos únicamente cuando el perfil solicitado sea
  Goleador/Asistidor.
- No se necesita `@DDD-Designer`: es un filtro nuevo sobre un endpoint de lectura existente,
  sin entidades ni value objects de dominio nuevos (regla explícita del Architecture-Engineer:
  "nuevo filtro en endpoint existente" no dispara DDD).

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Reutilizar el query param existente `bonus_label`, ampliando sus valores válidos a `{"Promesa", "Veterano", "Goleador", "Asistidor"}` | Crear un query param nuevo y separado (ej. `stat_profile`) | El frontend expone un único selector "Perfil" de valor único. Un segundo param duplicaría wiring (use case + 4 métodos de repository) para un concepto que en la UI ya es "un solo filtro de perfil". No hay compatibilidad hacia atrás que romper: es una ampliación aditiva de valores aceptados. |
| Función pura nueva `_stat_profile_filter(profile_label, goals_col, assists_col)` en `sfa_score_repository.py`, separada de `_bonus_label_filter` | Extender `_bonus_label_filter` para que también resuelva Goleador/Asistidor | `_bonus_label_filter` encapsula la lógica de bono B1 por edad (young_pts vs veteran_pts). Goleador/Asistidor es un umbral simple sobre conteos de goles/asistencias — un concepto de dominio no relacionado. Mezclarlos en una función complicaría lectura y testing. |
| Dispatch explícito en los 4 métodos: usar `_bonus_label_filter` si `bonus_label in {"Promesa", "Veterano"}`, usar `_stat_profile_filter` si `bonus_label in {"Goleador", "Asistidor"}` | Un único filtro combinado que intente resolver ambos casos internamente | Mantiene cada función con una sola responsabilidad y hace explícito en el call site qué tipo de filtro se está aplicando. |
| En `get_ranking`/`get_ranking_all_seasons`: aplicar `_stat_profile_filter` directo sobre `agg.c.sum_goals`/`agg.c.sum_assists` (ya calculados en el subquery `agg`) | Crear un subquery nuevo también para estos dos métodos | `agg` ya agrega goals/assists por jugador en el mismo scope filtrado; no hay necesidad de un join adicional. |
| En `get_ranking_total`/`get_ranking_total_all_seasons`: crear un subquery nuevo `stat_agg` (agrega `sum_goals`/`sum_assists` por `player_id` con los mismos `score_filters`), unido a `inner` (y a `exact_stmt` cuando `position is not None`) vía `outerjoin` + `.where()` | Aplicar el umbral con `.having()` directamente sobre `inner` | Mantiene el mismo patrón ya establecido en el archivo para `b1_agg` (subquery pre-agregada + outerjoin + where), en vez de introducir un patrón nuevo (`.having()`) que el resto del código no usa. |
| Solo actualizar el `description` del Query param `bonus_label` en el router — sin nuevo parámetro ni cambios de schema | Agregar un schema/enum Pydantic nuevo para validar los 4 valores | El comportamiento actual de `bonus_label` ya es un string libre sin validación estricta a nivel de schema (valores no reconocidos simplemente no filtran nada); mantener esa consistencia evita una validación asimétrica entre los 4 valores. |

## Domain Model

No aplica. No se crean entidades, value objects ni protocols de dominio nuevos.

## Integraciones externas

No aplica. No hay APIs externas ni proveedores nuevos involucrados; el filtro opera
exclusivamente sobre datos ya persistidos en `sfa_season_scores` / `player_event_scores`.
