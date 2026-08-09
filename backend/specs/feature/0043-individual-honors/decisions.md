# Palmares individual

## Contexto de negocio

SFA muestra logros colectivos obtenidos por el equipo, pero no conserva reconocimientos
individuales derivados de las estadisticas de una temporada o torneo. La ficha del jugador debe
incorporar un bloque "Palmares individual" debajo de "Palmares" y reconocer al maximo goleador,
maximo asistidor, mejor regateador y mayor ganador de duelos del periodo, Mundial, Champions y
ligas nacionales. Cada honor aporta puntos al ranking visible y explica con datos por que se otorgo.

## Restricciones

- Los goles, asistencias, regates, duelos y minutos ya existen en `player_stats`; no se agregan providers.
- Los periodos compuestos usan `AwardPeriodScope`: 2025/2026 incluye clubes 2025 y Mundial 2026.
- Los puntos deben pertenecer a una `ScoringRulesVersion` y no pueden sobrescribir bonos colectivos.
- Un recalculo del mismo scope debe ser idempotente y reemplazar resultados anteriores de esa version.
- El porcentaje de regates requiere intentos y minutos minimos para evitar ganadores de muestra pequena.
- Los honores por competicion se limitan a Mundial, Champions League y ligas nacionales configuradas.
- El ranking filtrado por competicion solo suma honores de esa competicion; el ranking general suma
  los honores globales y los de las competiciones incluidas en el scope.
- La suma de puntos de honores se limita a 8000 por jugador y scope; todos los honores siguen visibles.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Crear el subdominio `individual_honors` | Reutilizar `competition_achievements` | Los logros colectivos distribuyen puntos por participacion de plantilla; un honor individual tiene ganador, metrica y desempate propios. |
| Persistir resultados por `scope_key` y version | Calcularlos en cada GET | Permite auditoria, idempotencia, explicaciones y rankings estables. |
| Guardar `raw_bonus_pts` y `awarded_bonus_pts` | Agregar una columna a `sfa_season_scores` | Los honores globales no pertenecen a una sola competicion y un rebuild de scores no debe borrarlos. |
| Aplicar el limite de 8000 durante la inferencia del scope | Clampear solo en frontend | El ranking, API y ficha deben compartir exactamente el mismo total. |
| Resolver ganadores en un use case usando candidatos agregados del repository | Poner reglas de desempate en SQL | Las reglas de negocio quedan testeables y separadas del adaptador PostgreSQL. |
| Un ganador determinista por honor | Premios compartidos en la primera version | Los desempates acordados permiten un resultado unico y un presupuesto de puntos predecible. |
| Exponer `/players/{id}/individual-honors` | Mezclar DTOs con `/achievements` | Mantiene separados palmares colectivo e individual y permite evolucionar cada contrato. |
| Agregar los puntos en las consultas read-side del ranking | Crear eventos de scoring sinteticos | Los honores son derivados de cierre de periodo, no acciones atomicas de partido. |

## Domain Model

### Bounded context

Nuevo subdominio `individual_honors`. Se relaciona con scoring porque concede puntos versionados,
pero no modifica `ActionType`, multiplicadores ni `SFAScoringService`: representa reconocimientos
derivados al cerrar un conjunto de partidos.

### Nuevas entidades

- `IndividualHonor` representa un reconocimiento persistido para un jugador dentro de un scope.
  - Identidad: `id` de persistencia.
  - Campos: jugador, scope, tipo, competicion opcional, temporada fuente, version de reglas,
    valor principal, total de intentos opcional, porcentaje opcional, puntos base, puntos otorgados
    y detalles de calculo.
  - Invariantes: IDs positivos; `scope_key` no vacio; valores y puntos no negativos;
    `awarded_bonus_pts <= raw_bonus_pts`; porcentajes entre 0 y 1; una metrica de ratio requiere total.
  - Unicidad: `(scope_key, context_key, honor_type, rules_version_id)`; cada contexto tiene un
    unico ganador por tipo de honor.

### Nuevos value objects

- `IndividualHonorType`: `top_scorer`, `top_assister`, `best_dribbler`, `duel_king`.
- `HonorScopeCategory`: `award_period`, `world_cup`, `champions_league`, `domestic_league`.
- `HonorCandidateStats`: estadisticas agregadas inmutables de un jugador dentro de una fuente.

### Reglas de seleccion

- Maximo goleador: goles, luego asistencias, luego menos minutos y finalmente `player_id`.
- Maximo asistidor: asistencias, luego goles, luego menos minutos y finalmente `player_id`.
- Mejor regateador: porcentaje `dribbles_won / dribbles_attempts`, luego regates ganados,
  menos minutos y `player_id`; exige los minimos configurados por categoria.
- Rey de los duelos: duelos ganados, luego porcentaje de duelos, menos minutos y `player_id`;
  exige el minimo de minutos configurado.
- No se crea un honor de goles o asistencias si el maximo es cero.
- El limite por scope se aplica en orden de puntos base descendente y puede reducir parcialmente
  el ultimo honor que completa los 8000 puntos.

### Cambios en scoring

No se agregan `ActionType` ni entradas a `BASE_POINTS_TABLE`. `ScoringConfig` incorpora mapas
versionados para puntos, umbrales y limite de honores. Los defaults acordados son:

| Categoria | Goleador | Asistidor | Regateador | Duelos |
|---|---:|---:|---:|---:|
| Periodo completo | 3000 | 2500 | 1500 | 1200 |
| Mundial | 3000 | 2200 | 1500 | 1200 |
| Champions | 2200 | 1700 | 1200 | 1000 |
| Liga nacional | 1200 | 1000 | 700 | 600 |

### Ubicacion propuesta

- `domain/individual_honors.py`: enums, entidad, candidatos, resultados y port.
- `application/use_cases/infer_individual_honors.py`: seleccion, puntos y limite por scope.
- `application/use_cases/get_player_individual_honors.py`: lectura por jugador y scope.
- `infrastructure/models/individual_honors/models.py`: persistencia SQLAlchemy.
- `infrastructure/repositories/individual_honor_repository.py`: candidatos, reemplazo y lectura.

## Flujo

1. El recalculo termina de reconstruir scores y logros colectivos.
2. El motor resuelve el `AwardPeriodScope` solicitado y su version comun.
3. El repository agrega `player_stats` para todas las fuentes del periodo y para cada competicion elegible.
4. El use case elige cuatro ganadores por contexto, asigna puntos y aplica el limite por jugador.
5. El repository reemplaza atomicamente los honores del scope/version.
6. Las consultas de ranking suman `awarded_bonus_pts` segun scope y filtro de competicion.
7. La ficha consulta los honores y los muestra debajo del palmares colectivo con evidencia y puntos.

## Integraciones externas

No hay integraciones nuevas. La feature usa exclusivamente PostgreSQL y datos ya ingeridos.
