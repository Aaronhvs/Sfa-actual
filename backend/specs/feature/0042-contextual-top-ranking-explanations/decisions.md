# Explicaciones contextuales del Top 3

## Contexto de negocio

El carrusel "Por que este puesto" solo aparece en la vista independiente del Mundial. SFA debe
mostrar la misma lectura editorial en todas las temporadas y explicar el ranking que el usuario
esta viendo. Si se filtra Champions, posicion o perfil, la evidencia y el Top 3 deben pertenecer
a ese contexto; no se puede reutilizar una explicacion del ranking global.

## Restricciones

- El ranking y la explicacion deben usar el mismo `scope_key`, version de reglas y filtros.
- La busqueda por nombre no usa layout Top 3, por lo que no genera explicaciones.
- Las combinaciones de filtros son abiertas y no se pueden precalcular todas con IA.
- Una visita publica no debe disparar gasto externo ni escrituras sin limite.
- Las explicaciones editoriales cacheadas siguen siendo preferentes cuando coinciden exactamente.
- La ausencia de cache no puede dejar vacio el componente: debe existir fallback determinista.
- El Mundial, los periodos compuestos y las temporadas fisicas conservan sus fuentes reales.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Extender `RankingExplanationRequestDTO` con `scope_key`, `position` y `bonus_label` | Inferir el contexto desde `season` | `season=2026` es ambiguo y los filtros cambian el Top 3. |
| Resolver el ranking contextual en application usando `SeasonRepositoryProtocol` y `SFAScoreRepositoryProtocol` | Resolver scopes en el router o repository de explicaciones | Conserva Router -> Use Case -> Ports y una sola semantica de ranking. |
| Construir evidencia desde todas las fuentes de `AwardPeriodScope` | Usar solo la season fisica principal | `2025/2026` debe explicar club mas Mundial. |
| Consultar primero cache editorial y construir fallback determinista en lectura cuando falte | Encolar IA desde cada GET publico | Evita costo, abuso, carreras y pantallas vacias. |
| No persistir el fallback de combinaciones arbitrarias | Expandir ahora la tabla para cada filtro posible | El frontend cachea la respuesta y no se crea una matriz permanente de contextos efimeros. |
| Cachear/generar automaticamente el Top 3 general al cerrar un award period | Precalcular cada combinacion de filtros | El contexto principal merece texto editorial; los filtros quedan cubiertos inmediatamente por fallback. |
| Mostrar el carrusel cuando existe layout Top 3, en cualquier season y con filtros salvo busqueda | Mantenerlo exclusivo del Mundial | El componente explica el ranking visible, no un torneo especifico. |

## Domain Model

No se agregan entidades, aggregates, ActionTypes ni value objects de scoring. Se reutilizan
`AwardPeriodScope`, `ScoreSource`, `RankingExplanationRequestDTO` y `RankedPlayerDTO`.

El contexto de explicacion es un DTO de aplicacion/lectura. Su invariante es operacional: ranking,
evidencia y texto reciben el mismo scope, version y filtros. Los filtros de posicion y perfil
seleccionan jugadores; las fuentes de evidencia siguen siendo las del scope y competencia activa.

## Flujo

1. El frontend solicita explicaciones con la misma season key, competencia, posicion y perfil.
2. El use case resuelve el scope y una version comun.
3. Busca explicaciones publicas cacheadas solo para el contexto compatible.
4. Si faltan, obtiene el Top 3 con los mismos filtros.
5. El repository arma score rows, stats, eventos y partidos desde las fuentes del scope.
6. El writer determinista devuelve una explicacion inmediata y no persistida.
7. Los recalculos de award period encolan la generacion editorial del Top 3 global.

## Integraciones externas

No se agregan integraciones. El provider OpenAI-compatible existente solo se usa en las tasks
administrativas ya controladas. El fallback publico no realiza llamadas externas.
