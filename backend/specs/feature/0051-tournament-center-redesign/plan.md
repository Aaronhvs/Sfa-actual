# Plan: Centro de torneos y detalle de competicion

## Backend

- [x] Agregar DTOs frozen de dashboard y grupos de competicion en `domain/ports.py`.
- [x] Ampliar `TournamentRepositoryProtocol` con lectura de fechas y fixtures agrupados.
- [x] Implementar consulta de fecha exacta y fechas adyacentes en `TournamentRepository`.
- [x] Crear `GetTournamentDashboardUseCase` con resolucion de hoy/proxima/anterior.
- [x] Exponer `GET /tournaments/dashboard` antes de la ruta dinamica por id.
- [x] Agregar schemas Pydantic del dashboard sin filtrar modelos ORM.
- [x] Registrar el use case en `core/dependencies.py`.
- [x] Cubrir fecha actual, proxima, pasada, explicita y temporada vacia con tests.
- [x] Agregar ejemplos validos y errores en `http/tournaments.http`.

## Frontend

- [x] Agregar tipos y cliente para el dashboard de torneos.
- [x] Convertir `/torneos` en portada de tres columnas responsive.
- [x] Ordenar editorialmente Champions, ligas principales y resto de competiciones.
- [x] Permitir navegar entre fechas disponibles y volver a la fecha mas cercana.
- [x] Agrupar partidos por competicion con estado, hora, marcador y escudos.
- [x] Mostrar top 3 SFA de la temporada en el panel lateral.
- [x] Crear `/torneos/:competitionId` como detalle compartible.
- [x] Implementar tabs Resumen, Tabla, Partidos y Cruces con controles accesibles.
- [x] Derivar J/G/E/P/GF/GC/DG desde marcadores finalizados.
- [x] Agregar filtros de partidos por fecha, jornada y equipo.
- [x] Preservar estados loading, error y vacio en ambas rutas.
- [x] Actualizar SEO para rutas de detalle.
- [x] Adaptar el layout a escritorio, tablet y movil sin paneles anidados.

## Verificacion

- [x] Ejecutar tests backend enfocados y suite completa (`547 passed`).
- [x] Ejecutar `flake8`, `isort --check-only` y `git diff --check`.
- [x] Ejecutar `npm run build`.
- [x] Verificar portada y detalle con Playwright en escritorio, 768px y 390px.
- [x] Confirmar navegacion por teclado, foco visible y ausencia de overflow horizontal.

## Agent Routing Brief

**DDD Designer needed:** no

La feature agrega un read model y reorganiza presentacion sobre fixtures, standings y ranking ya
existentes. No modifica persistencia ni reglas de scoring.
