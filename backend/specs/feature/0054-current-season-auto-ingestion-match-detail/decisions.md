# 0054 - Current Season Auto Ingestion And Match Detail

## Contexto de negocio

La temporada de clubes 2026/2027 ya comenzo. El worker periodico sigue limitado al
Mundial 2026 y la experiencia completa de partido (cronologia, alineaciones,
estadisticas y rendimiento SFA) solo esta expuesta bajo rutas y DTOs del Mundial.

SFA debe ingerir automaticamente las competiciones de clubes configuradas para la
temporada API-Football `2026` y permitir abrir cualquier partido de esa temporada
desde Torneos con el mismo nivel de detalle que tuvo el Mundial.

## Restricciones

- API-Football identifica 2026/2027 como `season=2026`.
- La ingesta periodica solo puede activar pares `(league_id, season)` explicitamente
  aprobados; no debe ingerir competiciones desconocidas que aparezcan en el feed diario.
- Cronologia se persiste en `fixture_events` durante ingestion. Alineaciones y
  estadisticas son datos volatiles y se consultan bajo demanda con cache Redis.
- El endpoint de detalle solo acepta fixtures de clubes existentes en PostgreSQL para
  la temporada solicitada. No funciona como proxy de fixtures arbitrarios.
- El replay de ELO/scoring 2026 requiere semillas canonicas de clubes antes del primer
  recalculo productivo.
- Las rutas existentes del Mundial deben seguir funcionando durante la transicion.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Crear un bounded context generico de detalle de fixture para Torneos | Consultar `/wc` desde Torneos | Evita acoplar la temporada de clubes al contexto del Mundial |
| Mantener aliases de compatibilidad `WorldCup*DTO` | Reescribir todo el Mundial en un solo despliegue | Conserva contratos existentes mientras Torneos usa nombres genericos |
| Exponer `GET /tournaments/fixtures/{fixture_external_id}?season=2026` | Reutilizar `/wc/fixtures/{id}` desde el frontend | La URL expresa el contexto correcto y valida temporada/participant kind |
| Resolver y validar el fixture local antes de consultar API-Football | Consultar API-Football primero | Protege cuota y evita acceso a fixtures fuera de SFA |
| Activar una whitelist declarativa de competiciones club 2026 | Activar cualquier fixture del feed diario | Mantiene control de costo y alcance |
| Pasar los fixture IDs relevantes a la ingesta periodica | Reprocesar todos los partidos no finalizados de la competicion | Reduce llamadas de eventos/jugadores durante cada ciclo live |
| Reutilizar `MatchTimeline` y la pagina tactica existente | Crear una segunda UI de partido | Mantiene una experiencia unica y reduce divergencia visual |

## Limites arquitectonicos

- `domain/fixture_detail_ports.py`: DTOs genericos y
  `FixtureDetailRepositoryProtocol`.
- `application/use_cases/get_tournament_fixture_detail.py`: valida fixture local de
  club/temporada y obtiene el detalle compuesto.
- `infrastructure/repositories/fixture_detail_repository.py`: cache Redis, proveedor,
  cronologia persistida y enriquecimiento SFA.
- `infrastructure/providers/api_football.py`: parser generico
  `fetch_fixture_detail`; el nombre antiguo queda como wrapper compatible para que
  el repositorio historico del Mundial conserve su contrato.
- `api/v1/tournaments.py`: nuevo endpoint bajo Torneos.
- `tasks/ingest_today_task.py`: whitelist 2026/2027 y seleccion de fixtures relevantes.
- Frontend: ruta `/torneos/partido/:fixtureId`, tarjetas enlazables y pagina de detalle
  reutilizable fuera del Mundial.

## Integraciones externas

- `fixtures?id={fixture_id}` para metadatos y marcador.
- `fixtures/lineups?fixture={fixture_id}` para formaciones, titulares y suplentes.
- `fixtures/statistics?fixture={fixture_id}` para comparacion del partido.
- `fixtures/events?fixture={fixture_id}` ya forma parte de ingestion y alimenta
  `fixture_events`; no se consulta al leer el detalle.

## Compatibilidad y fallos

- Fixture inexistente, de otra temporada o de selecciones: `404` sin llamada externa.
- Detalle aun no publicado: se devuelven listas vacias con los empty states existentes.
- Fallo de API-Football: se conserva la politica de retry del provider.
- El endpoint WC conserva su response y ruta actuales mediante aliases y el wrapper compatible del provider.
