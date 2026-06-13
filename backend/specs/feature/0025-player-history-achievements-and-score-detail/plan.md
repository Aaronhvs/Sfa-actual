# Plan: Historico de jugador, recorridos por competicion y detalle de puntos

## Archivos a crear

- [ ] `src/sfa/application/use_cases/get_player_achievements.py` - orquestar la lectura de recorridos por jugador y alcance temporal.
- [ ] `tests/use_cases/test_get_player_achievements.py` - cubrir temporada concreta, historico, version de reglas resuelta y lista vacia.
- [ ] `frontend/src/components/player/CompetitionJourney.tsx` - renderizar trofeos y fases alcanzadas.
- [ ] `frontend/src/components/player/CompetitionJourney.css` o bloque equivalente en el stylesheet existente - estilos responsive y accesibles de la nueva seccion.

## Archivos a modificar

- [ ] `src/sfa/domain/scoring_ports.py` - agregar `PlayerCompetitionAchievementDTO` y extender `CompetitionAchievementRepositoryPort`.
- [ ] `src/sfa/domain/ports.py` - hacer opcionales los filtros de `get_player_season_stats` y permitir `competition_id` nullable en el DTO agregado.
- [ ] `src/sfa/infrastructure/repositories/competition_achievement_repository.py` - implementar la consulta de recorridos por jugador.
- [ ] `src/sfa/infrastructure/repositories/player_event_repository.py` - agregar stats por alcance y normalizar filtros opcionales.
- [ ] `src/sfa/application/use_cases/get_player_season_stats.py` - traducir `season=all` a alcance historico.
- [ ] `src/sfa/application/use_cases/get_player_events.py` - traducir `season=all` a ausencia de filtro.
- [ ] `src/sfa/application/use_cases/get_player_fixtures.py` - traducir `season=all` a ausencia de filtro.
- [ ] `src/sfa/core/dependencies.py` - cablear `GetPlayerAchievementsUseCase`.
- [ ] `src/sfa/api/v1/players.py` - exponer logros y flexibilizar el endpoint de stats.
- [ ] `src/sfa/api/v1/schemas/players.py` - agregar schema de recorridos y ajustar `competition_id` de stats.
- [ ] `http/players.http` - documentar casos de temporada concreta, `all`, stats globales y recorridos.
- [ ] `tests/use_cases/test_get_player_fixtures.py` - comprobar la normalizacion de `all`.
- [ ] `tests/use_cases/test_get_player_events.py` - comprobar la normalizacion de `all`.
- [ ] `tests/use_cases/test_get_player_season_stats.py` - cubrir todas las combinaciones de alcance y formulas agregadas.
- [ ] `frontend/src/types/index.ts` - agregar el contrato de recorridos y hacer nullable el identificador de competicion agregado.
- [ ] `frontend/src/api/client.ts` - agregar fetch de recorridos y solicitar stats por alcance sin agregacion local.
- [ ] `frontend/src/pages/PlayerPage.tsx` - eliminar la agregacion parcial en React y cargar todos los recursos con el mismo selector.
- [ ] `frontend/src/components/player/PerformanceChart.tsx` - completar etiquetas del breakdown y asegurar detalle por hover, focus y click.
- [ ] `frontend/src/index.css` - integrar estilos si el proyecto mantiene el CSS del componente en el stylesheet global.

### Ampliacion: bonus real por logro

- [ ] `src/sfa/domain/scoring_ports.py` - agregar `bonus_pts` al DTO y exigir `rules_version_id` en la lectura de recorridos.
- [ ] `src/sfa/infrastructure/repositories/competition_achievement_repository.py` - seleccionar `final_bonus` y filtrar por la version de reglas resuelta.
- [ ] `src/sfa/application/use_cases/get_player_achievements.py` - resolver la version solicitada o el default activo sin recalcular bonuses.
- [ ] `src/sfa/core/dependencies.py` - inyectar la version activa como default del use case.
- [ ] `src/sfa/api/v1/players.py` - aceptar el query param opcional `rules_version_id`.
- [ ] `src/sfa/api/v1/schemas/players.py` - exponer `bonus_pts` como numero no negativo.
- [ ] `tests/use_cases/test_get_player_achievements.py` - cubrir version default, override y propagacion del bonus persistido.
- [ ] `http/players.http` - documentar consultas de achievements con version activa y explicita.
- [ ] `frontend/src/types/index.ts` - incorporar `bonus_pts` al contrato del recorrido.
- [ ] `frontend/src/api/client.ts` - enviar la misma version de reglas usada por el perfil.
- [ ] `frontend/src/components/player/CompetitionJourney.tsx` - mostrar el bonus real junto al logro.

## Checklist de implementacion

- [ ] 1. Ejecutar `pytest tests/ -x` antes de modificar codigo y registrar cualquier fallo preexistente.
  Criterio de completitud: existe un resultado reproducible de baseline y los fallos ajenos al spec quedan identificados.

- [ ] 2. Agregar `PlayerCompetitionAchievementDTO` como frozen dataclass.
  Criterio de completitud: contiene exactamente los campos definidos en `decisions.md` y no importa modelos ORM.

- [ ] 3. Extender `CompetitionAchievementRepositoryPort` con `get_player_achievements`.
  Criterio de completitud: el Protocol expresa `player_id` obligatorio y `season` opcional.

- [ ] 4. Implementar la consulta de recorridos en `CompetitionAchievementRepository`.
  Criterio de completitud: une bonus, logro, competicion y equipo; filtra por jugador y
  version de reglas; aplica temporada solo cuando no es `None`.

- [ ] 5. Derivar `title_count` exclusivamente desde `phase`.
  Criterio de completitud: `winner` y `champion` devuelven `1`; cualquier otra clave devuelve `0`.

- [ ] 6. Ordenar recorridos de forma determinista.
  Criterio de completitud: temporada descendente y nombre de competicion ascendente, sin duplicados.

- [ ] 7. Crear `GetPlayerAchievementsUseCase`.
  Criterio de completitud: `season=all` se convierte a `None`; una temporada concreta se conserva; el resultado del port se retorna sin acceso a infraestructura.

- [ ] 8. Agregar factory de `GetPlayerAchievementsUseCase` en `core/dependencies.py`.
  Criterio de completitud: el wiring usa `get_competition_achievement_repository` y no se instancia infraestructura en el router.

- [ ] 9. Agregar `PlayerCompetitionAchievementSchema`.
  Criterio de completitud: refleja el DTO completo y valida `title_count` como entero no negativo.

- [ ] 10. Exponer `GET /api/v1/players/{player_id}/achievements`.
  Criterio de completitud: acepta `season` opcional, devuelve `200` con lista vacia y no realiza SQL ni logica de presentacion en el router.

- [ ] 11. Hacer opcionales `competition_id` y `season` en el metodo de stats del port.
  Criterio de completitud: los tipos del Protocol, use case y repositorio coinciden.

- [ ] 12. Mantener `season` como query param requerido del endpoint de stats y aceptar `all`.
  Criterio de completitud: `all` llega al repositorio como `None`; una temporada concreta mantiene su valor.

- [ ] 13. Hacer `competition_id` opcional en el endpoint de stats.
  Criterio de completitud: al omitirlo no se agrega predicado por competicion; al enviarlo se conserva el comportamiento filtrado existente.

- [ ] 14. Reescribir la agregacion SQL de stats para soportar cuatro alcances.
  Criterio de completitud: funcionan temporada+competicion, temporada+todas las competiciones, historico+competicion e historico+todas las competiciones.

- [ ] 15. Calcular correctamente estadisticas derivadas.
  Criterio de completitud: sumas usan todas las filas del alcance; precision de pases es ponderada por `passes_total`; ratios de regate y duelo usan totales globales; rating usa promedio de las apariciones con rating.

- [ ] 16. Ajustar `PlayerSeasonStatsDTO` y schema para agregados globales.
  Criterio de completitud: `competition_id=None` es valido y `season="all"` identifica el historico.

- [ ] 17. Normalizar `season=all` en `GetPlayerEventsUseCase`.
  Criterio de completitud: el repositorio recibe `season=None` y retorna eventos de todas las temporadas.

- [ ] 18. Normalizar `season=all` en `GetPlayerFixturesUseCase`.
  Criterio de completitud: el repositorio recibe `season=None`, retorna fixtures historicos y mantiene el breakdown activo.

- [ ] 19. Verificar consistencia entre `sfa_pts` y breakdown por fixture.
  Criterio de completitud: para fixtures con scores activos, la suma de `breakdown[*].pts` coincide con `sfa_pts` dentro de tolerancia de redondeo.

- [ ] 20. Actualizar `http/players.http`.
  Criterio de completitud: incluye ejemplos para stats globales de temporada, stats historicas, recorridos de temporada, recorridos historicos y jugador sin logros.

- [ ] 21. Escribir tests del use case de recorridos con Fake completo.
  Criterio de completitud: cubre temporada concreta, `all`, lista vacia y conformidad con el Protocol sin `MagicMock`.

- [ ] 22. Escribir tests de repositorio o integracion para aislamiento de versiones.
  Criterio de completitud: dos bonuses del mismo logro en versiones distintas producen un
  solo elemento con el valor de la version solicitada.

- [ ] 23. Ampliar tests de stats.
  Criterio de completitud: las cuatro combinaciones de alcance producen sumas y ratios esperados, y alcance sin filas retorna `None`.

- [ ] 24. Ampliar tests de events y fixtures.
  Criterio de completitud: `all` se normaliza a `None`, una temporada concreta no cambia y el breakdown sigue solicitandose por defecto.

- [ ] 25. Agregar tipo frontend `PlayerCompetitionAchievement`.
  Criterio de completitud: coincide con el schema HTTP y no contiene copy ni iconos de presentacion.

- [ ] 26. Agregar `fetchPlayerAchievements`.
  Criterio de completitud: incluye `season` en cache key y query; acepta `all`; propaga errores HTTP.

- [ ] 27. Simplificar la carga de stats en `PlayerPage`.
  Criterio de completitud: se elimina `SUM_FIELDS` y `aggregateSeasonStats`; se realiza una llamada sin `competition_id` para el alcance seleccionado.

- [ ] 28. Unificar el alcance temporal de la pagina.
  Criterio de completitud: detalle, stats, events, fixtures y achievements se solicitan con el mismo valor de selector y se actualizan juntos al cambiarlo.

- [ ] 29. Evitar estados mezclados durante cambios de temporada.
  Criterio de completitud: no se muestran stats o recorridos de la seleccion anterior mientras llegan los nuevos datos; errores parciales tienen estado controlado.

- [ ] 30. Crear `CompetitionJourney`.
  Criterio de completitud: aparece entre `StatBar` y `PerformanceChart`; muestra competicion, temporada y fase; usa trofeo y cantidad `1` cuando `title_count=1`.

- [ ] 31. Traducir fases solo en frontend.
  Criterio de completitud: existe mapa para claves conocidas y fallback legible para una clave desconocida.

- [ ] 32. Agrupar el historico de recorridos por temporada.
  Criterio de completitud: `season=all` distingue visualmente temporadas sin sumar fases ni titulos incompatibles.

- [ ] 33. Completar el detalle de la linea de tiempo.
  Criterio de completitud: cada punto muestra rival, fecha, total, y filas de accion con cantidad y puntos; `formatAction` queda definido o importado.

- [ ] 34. Mantener interaccion accesible del tooltip.
  Criterio de completitud: funciona con hover, focus, Enter o click para fijar, Escape para cerrar y labels accesibles que anuncian que existe desglose.

- [ ] 35. Verificar responsive de recorridos y tooltip.
  Criterio de completitud: no hay overflow horizontal a 320 px; el tooltip permanece dentro del viewport o cambia de alineacion.

- [ ] 36. Ejecutar tests backend.
  Criterio de completitud: `pytest tests/` pasa sin regresiones y la cobertura total permanece en al menos 80%.

- [ ] 37. Ejecutar calidad backend.
  Criterio de completitud: `flake8 src/ tests/` e `isort --check-only src/ tests/` terminan sin errores nuevos.

- [ ] 38. Ejecutar verificacion frontend.
  Criterio de completitud: `npm run build` termina correctamente y no hay referencia indefinida a `formatAction`.

- [ ] 39. Verificar end-to-end con una temporada concreta.
  Criterio de completitud: stats incluyen todas las competiciones de esa temporada; recorridos corresponden a esa temporada; timeline tiene partidos y breakdown.

- [ ] 40. Verificar end-to-end con `season=all`.
  Criterio de completitud: stats, events y fixtures contienen ambas temporadas disponibles;
  recorridos estan agrupados por temporada y pertenecen solo a la version de reglas resuelta.

### Checklist de ampliacion: bonus real por logro

- [ ] 41. Agregar `bonus_pts: float` a `PlayerCompetitionAchievementDTO`.
  Criterio de completitud: el campo representa exclusivamente
  `player_achievement_bonuses.final_bonus` y no un valor base o recalculado.

- [ ] 42. Extender `CompetitionAchievementRepositoryPort.get_player_achievements` con
  `rules_version_id: int` obligatorio.
  Criterio de completitud: el contrato impide consultar bonuses sin una version resuelta y
  mantiene `season` como filtro opcional.

- [ ] 43. Filtrar la consulta de recorridos por `PlayerAchievementBonusModel.rules_version_id`.
  Criterio de completitud: cada fila devuelta corresponde exactamente al jugador, logro y
  version solicitados; no se usa `DISTINCT`, `MAX`, suma ni orden temporal para elegir entre
  versiones.

- [ ] 44. Seleccionar `PlayerAchievementBonusModel.final_bonus` como `bonus_pts`.
  Criterio de completitud: el repositorio convierte el decimal persistido a `float` en el
  DTO y no consulta `calculation_details` para derivar el resultado.

- [ ] 45. Ampliar `GetPlayerAchievementsUseCase` con version de reglas.
  Criterio de completitud: el constructor acepta `default_rules_version_id`; `execute`
  acepta override opcional; el override tiene prioridad y la version resuelta se pasa al
  repositorio sin ejecutar ninguna formula.

- [ ] 46. Definir el comportamiento cuando no existe version resuelta.
  Criterio de completitud: el use case retorna lista vacia sin consultar bonuses de varias
  versiones ni seleccionar una version implicitamente.

- [ ] 47. Inyectar la version activa en `get_player_achievements_use_case`.
  Criterio de completitud: `core/dependencies.py` usa
  `ScoringRulesVersionRepository.get_active_version()` y construye el use case con su id,
  siguiendo el patron de `get_player_detail_use_case`.

- [ ] 48. Aceptar `rules_version_id` opcional en el endpoint de achievements.
  Criterio de completitud: el router lo delega al use case; no consulta repositorios ni
  resuelve versiones directamente.

- [ ] 49. Agregar `bonus_pts` a `PlayerCompetitionAchievementSchema`.
  Criterio de completitud: Pydantic acepta decimales no negativos y la respuesta conserva
  todos los campos existentes.

- [ ] 50. Mantener compatibilidad del endpoint.
  Criterio de completitud: una llamada existente sin `rules_version_id` sigue respondiendo
  `200` y usa la version activa; `season=all` sigue eliminando solo el filtro temporal.

- [ ] 51. Actualizar los Fakes y tests unitarios del use case.
  Criterio de completitud: cubren version activa por default, override explicito,
  normalizacion de `all`, ausencia de version activa y propagacion intacta de `bonus_pts`.

- [ ] 52. Agregar prueba de repositorio para aislamiento entre versiones.
  Criterio de completitud: dos bonuses del mismo logro con versiones y valores distintos
  producen un solo recorrido con el `final_bonus` de la version solicitada.

- [ ] 53. Verificar que la lectura no altera scoring ni persistencia.
  Criterio de completitud: la ruta no invoca `CalculateAchievementBonusesUseCase`, no
  actualiza `sfa_season_scores` y no escribe en `player_achievement_bonuses`.

- [ ] 54. Actualizar el contrato frontend y `CompetitionJourney`.
  Criterio de completitud: cada tarjeta muestra `bonus_pts` formateado como puntos SFA y no
  calcula el valor desde fase, trofeo, participacion o configuracion.

- [ ] 55. Mantener una unica version de reglas entre superficies.
  Criterio de completitud: detalle del jugador, ranking y achievements solicitan la misma
  `rules_version_id`, por lo que el bonus mostrado forma parte del total visible.

- [ ] 56. Verificar el endpoint con version activa y override.
  Criterio de completitud: para un registro conocido, `bonus_pts` coincide exactamente con
  `player_achievement_bonuses.final_bonus` en DB para ambas consultas.

- [ ] 57. Ejecutar la verificacion de regresion de la ampliacion.
  Criterio de completitud: tests focalizados de achievements y build frontend pasan; los
  fallos preexistentes del suite completo se registran sin atribuirlos a este cambio.

## Agent Routing Brief

**DDD Designer needed:** no

La feature agrega DTOs de lectura, filtros opcionales y un use case de consulta sobre modelos
existentes. No introduce entidades, value objects, aggregates, invariantes de negocio ni
cambios al dominio de scoring. La clasificacion visual de fases y trofeos se mantiene fuera
del dominio y el algoritmo de puntuacion no se modifica.

## Verificacion

1. `GET /api/v1/players/{id}/stats?season=2025` devuelve el agregado de todas las competiciones de 2025.
2. `GET /api/v1/players/{id}/stats?season=all` devuelve todas las temporadas y `competition_id=null`.
3. `GET /api/v1/players/{id}/events?season=all` y `GET /api/v1/players/{id}/fixtures?season=all` devuelven datos historicos.
4. `GET /api/v1/players/{id}/achievements?season=2025` devuelve recorridos unicos de esa temporada.
5. `GET /api/v1/players/{id}/achievements?season=all` devuelve recorridos de todas las
   temporadas para una unica version de reglas.
6. En la pagina del jugador, cambiar entre temporada concreta y Total historico actualiza todas las secciones con el mismo alcance.
7. Un logro `winner` o `champion` muestra trofeo y cantidad `1`; una eliminacion muestra la fase alcanzada.
8. Hover, focus o click sobre un partido muestra las acciones y puntos cuya suma explica el total del partido.
9. `GET /api/v1/players/{id}/achievements?season=2025&rules_version_id=<id>` devuelve
   `bonus_pts` igual al `final_bonus` persistido para cada logro de esa version.
10. Omitir `rules_version_id` devuelve los bonuses de la version activa y no combina
    registros de otras versiones.
11. `CompetitionJourney` muestra el bonus individual recibido junto al trofeo o fase, y el
    valor coincide con la porcion de bonus incluida en el total SFA de la misma version.
