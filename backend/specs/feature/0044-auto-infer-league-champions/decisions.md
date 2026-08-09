# Inferencia automatica de campeones de liga

## Contexto de negocio

El pipeline de recalculo infiere logros de copas desde fixtures eliminatorios, pero las ligas
domesticas dependen de un registro manual. `RefreshLeagueAchievementBonusesUseCase` solo actualiza
el valor de logros existentes; no crea el logro `champion`. Por eso los jugadores de campeones
como PSG o Arsenal pueden terminar la temporada sin puntos de liga aunque la tabla final ya este
ingerida.

La inferencia debe cerrar esa asimetria: cuando una liga tenga una tabla final completa, el primer
clasificado debe generar automaticamente un `CompetitionAchievement` de fase `champion` antes de
calcular los bonus de sus jugadores.

## Restricciones

- La arquitectura sigue Router/Task -> Use Case -> Port -> Repository; no se consulta SQLAlchemy
  desde aplicacion.
- No se debe premiar a un lider provisional durante una temporada activa.
- La tabla `standing_snapshots` conserva posicion, puntos y un `matchday` equivalente al maximo de
  partidos jugados informado por API-Football.
- Para las ligas round-robin ingeridas, una tabla se considera completa cuando su ultimo matchday
  alcanza `2 * (numero_de_equipos - 1)`.
- Las ligas con formatos especiales o snapshots incompletos se omiten de forma segura y mantienen
  disponible el registro manual.
- La inferencia debe ser idempotente y debe dejar un solo campeon por competicion, temporada y fase.
- El recalculo de bonos debe limpiar detalles y totales previos de la competicion para no conservar
  puntos de un campeon reemplazado.
- No se agregan endpoints, providers ni migraciones.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Crear `InferLeagueChampionsUseCase` | Ampliar la inferencia KO con standings | Mantiene separadas las reglas de copas y ligas y respeta la responsabilidad de cada use case. |
| Leer candidatos finales mediante un metodo del `CompetitionAchievementRepositoryPort` | Usar `StandingRepositoryProtocol.get_standings` | El DTO publico de standings no contiene `competition_id` ni `team_id`, necesarios para registrar el logro. |
| Definir `LeagueChampionCandidateDTO` en `scoring_ports.py` | Retornar tuplas sin tipo | Hace explicitos nombre, equipo, matchday y cantidad de participantes sin crear una entidad de negocio nueva. |
| El repository devuelve lider, matchday y cantidad de equipos; el use case valida el cierre | Confiar solo en `position = 1` | La regla de cierre queda en aplicacion y evita conceder puntos al lider provisional. |
| Reemplazar de forma atomica la fase `champion` antes del upsert | Conservar cualquier registro manual previo | Garantiza un solo campeon y corrige registros stale sin borrar runner-up o top-4. |
| Reconstruir los bonos de cada competicion desde cero | Conservar y sobrescribir solo filas coincidentes | Elimina puntos residuales si cambia el campeon o deja de aplicar un logro. |
| Ejecutar la inferencia antes de `RefreshLeagueAchievementBonusesUseCase` | Ejecutarla despues del calculo | Los nuevos logros deben existir y tener config vigente antes de distribuir puntos. |

## Domain Model

No se requieren nuevas entidades ni value objects. Se agrega un DTO inmutable de lectura:

- `LeagueChampionCandidateDTO`
  - `competition_id: int`
  - `competition_name: str`
  - `team_id: int`
  - `season: str`
  - `matchday: int`
  - `team_count: int`
  - `regular_fixture_count: int`
  - `pending_fixture_count: int`

El logro persistido sigue siendo `CompetitionAchievement` con fase canonica `champion`.

## Flujo

1. El recalculo reconstruye los scores base.
2. La inferencia KO registra logros de copas.
3. `InferLeagueChampionsUseCase` consulta los ultimos lideres de ligas conocidas y valida que la tabla este completa.
4. El use case resuelve puntos `domestic_league.champion` y peso por competicion desde la rules version.
5. El repository reemplaza el campeon de esa fase y hace upsert del logro correcto.
6. El refresh actualiza otros logros manuales de liga que puedan existir.
7. `CalculateAchievementBonusesUseCase` limpia los bonos previos de la competicion y distribuye de
   nuevo los puntos a los jugadores participantes.

## Integraciones externas

Ninguna nueva. Se usan snapshots ya ingeridos desde API-Football y PostgreSQL.
