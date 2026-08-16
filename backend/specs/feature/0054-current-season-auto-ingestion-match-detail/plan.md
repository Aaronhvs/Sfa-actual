# Plan: 0054 - Current Season Auto Ingestion And Match Detail

## Archivos a crear

- [x] `src/sfa/domain/fixture_detail_ports.py` - DTOs y port genericos de detalle.
- [x] `src/sfa/application/use_cases/get_tournament_fixture_detail.py` - validacion y composicion del detalle.
- [x] `src/sfa/infrastructure/repositories/fixture_detail_repository.py` - cache, eventos y puntos SFA.
- [x] `tests/use_cases/test_get_tournament_fixture_detail.py` - happy path y rechazos de alcance.
- [x] `frontend/src/pages/TournamentMatchPage.tsx` - detalle de partido en Torneos.

## Archivos a modificar

- [x] `src/sfa/domain/world_cup_ports.py` - aliases compatibles hacia DTOs genericos.
- [x] `src/sfa/domain/ports.py` - lookup local de fixture dentro del port de Torneos.
- [x] `src/sfa/application/use_cases/get_tournaments.py` - soporte de lookup local.
- [x] `src/sfa/infrastructure/providers/api_football.py` - parser de detalle generico.
- [x] `src/sfa/infrastructure/repositories/tournament_repository.py` - lookup por external ID, season y clubes.
- [x] `src/sfa/core/dependencies.py` - wiring de repositorio y use case.
- [x] `src/sfa/api/v1/schemas/tournaments.py` - schemas de detalle.
- [x] `src/sfa/api/v1/tournaments.py` - endpoint de fixture.
- [x] `src/sfa/tasks/ingest_today_task.py` - competiciones activas 2026 y fixture IDs relevantes.
- [x] `src/sfa/tasks/ingestion_tasks.py` - parametro opcional de fixtures objetivo.
- [x] `src/sfa/application/use_cases/ingest_competition.py` - limitar fase 3 cuando hay objetivo.
- [x] `tests/use_cases/test_ingest_stats_event.py` - permitir calendarios sin standings publicados.
- [x] `frontend/src/api/client.ts` - cliente de detalle de Torneos.
- [x] `frontend/src/types/index.ts` - aliases/tipos genericos de detalle.
- [x] `frontend/src/components/tournaments/TournamentFixtureRow.tsx` - enlace accesible.
- [x] `frontend/src/App.tsx` - ruta de partido.
- [x] `frontend/src/index.css` - ajustes de enlace y contexto de Torneos.
- [x] `http/tournaments.http` - ejemplo del endpoint nuevo.

## Checklist de implementacion

- [x] Registrar estado basal de tests antes de modificar codigo.
- [x] Extraer DTOs de detalle sin romper imports `WorldCup*` existentes.
- [x] Generalizar el parser API-Football sin duplicar requests ni normalizacion.
- [x] Implementar repositorio generico con las TTL live/upcoming/completed actuales.
- [x] Adjuntar eventos persistidos ordenados y puntos SFA de la version activa.
- [x] Validar que el fixture pertenece a clubes y a la temporada solicitada antes del fetch externo.
- [x] Agregar use case, DI, schemas, endpoint y archivo HTTP.
- [x] Activar Super Cup, Community Shield, ligas principales y competiciones UEFA para season 2026.
- [x] Hacer que la tarea diaria envie solo IDs live/recientes a la fase costosa de ingestion.
- [x] Mantener ingestas manuales/full sin filtro cuando no se pasa una lista objetivo.
- [x] Desacoplar la importacion de fixtures de la disponibilidad de standings.
- [x] Crear pagina de detalle generica reutilizando timeline, cancha, alineaciones y estadisticas.
- [x] Enlazar filas de partidos de Torneos y mantener navegacion de regreso contextual.
- [x] Escribir tests de use case, whitelist/seleccion y parser compatible.
- [x] Ejecutar tests backend focalizados y chequeos estaticos relevantes.
- [x] Ejecutar build frontend y verificar desktop/mobile con Playwright.
- [x] Documentar bootstrap y despliegue VPS, incluida la precondicion de ELO 2026.

## Agent Routing Brief

**DDD Designer needed:** no

El cambio crea DTOs de lectura y coordina adaptadores existentes. No introduce nuevas
entidades con invariantes, aggregates ni reglas de scoring.

## Verificacion

1. Un fixture club season 2026 existente responde por
   `GET /api/v1/tournaments/fixtures/{external_id}?season=2026`.
2. Un fixture World Cup o de season distinta responde 404 sin consultar API-Football.
3. Una fila de Torneos abre `/torneos/partido/{external_id}?season=2026` y muestra
   cronologia, formaciones y estadisticas.
4. `ingest_today_task` ignora World Cup finalizado y solo encola competiciones club
   2026 aprobadas con partidos live o terminados recientemente.
5. La ruta historica `/api/v1/wc/fixtures/{id}` continua respondiendo.
