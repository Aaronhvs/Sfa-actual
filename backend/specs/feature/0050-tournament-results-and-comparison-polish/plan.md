# Plan: Torneos de temporada y correccion del comparador

## Archivos a crear

- [x] `src/sfa/application/use_cases/get_tournaments.py` - catalogo y detalle de torneos.
- [x] `src/sfa/infrastructure/repositories/tournament_repository.py` - consultas locales de temporada.
- [x] `src/sfa/api/v1/tournaments.py` - endpoints publicos de lectura.
- [x] `src/sfa/api/v1/schemas/tournaments.py` - schemas del catalogo, fixtures y tabla.
- [x] `tests/use_cases/test_get_tournaments.py` - resolucion de temporada, catalogo y detalle.
- [x] `http/tournaments.http` - ejemplos de ambos endpoints y errores.
- [x] `../frontend/src/pages/TournamentsPage.tsx` - pagina de resultados de temporada.

## Archivos a modificar

- [x] `src/sfa/domain/ports.py` - DTOs y port de lectura de torneos.
- [x] `src/sfa/core/dependencies.py` - wiring del repositorio y use cases.
- [x] `src/sfa/infrastructure/repositories/__init__.py` - exportar el repositorio.
- [x] `src/sfa/main.py` - registrar router y metadata.
- [x] `src/sfa/application/use_cases/compare_players.py` - incluir breakdown por fixture.
- [x] `tests/use_cases/test_compare_players.py` - exigir breakdown en las consultas.
- [x] `../frontend/src/types/index.ts` - tipos de torneos.
- [x] `../frontend/src/api/client.ts` - cliente de catalogo y detalle.
- [x] `../frontend/src/App.tsx` - ruta `/torneos` y compatibilidad `/mundial`.
- [x] `../frontend/src/components/layout/Navbar.tsx` - sustituir Mundial por Torneos.
- [x] `../frontend/src/components/layout/Footer.tsx` - acceso a Torneos.
- [x] `../frontend/src/components/shared/SeoController.tsx` - metadata de Torneos.
- [x] `../frontend/src/index.css` - estilos responsive de Torneos y pulido del comparador.

## Checklist de implementacion

- [x] Registrar baseline de pruebas backend y build frontend.
- [x] Agregar DTOs inmutables sin dependencias de infraestructura.
- [x] Resolver por defecto la temporada de clubes mas reciente con fixtures.
- [x] Listar solo competiciones activas y sus conteos de estado.
- [x] Devolver fixtures locales, ultima tabla y cruces en el detalle.
- [x] Mantener vacias, pero validas, las tablas no disponibles.
- [x] Registrar factories en `core/dependencies.py` y router en `main.py`.
- [x] Agregar ejemplos HTTP para catalogo, detalle y competicion inexistente.
- [x] Reemplazar la entrada Mundial por Torneos y preservar redirecciones antiguas.
- [x] Implementar estados loading, error y vacio en la pagina.
- [x] Mostrar fechas/resultados, tabla y cruces mediante tabs accesibles.
- [x] Solicitar breakdown por fixture en el comparador.
- [x] Verificar hat-tricks, dobletes de gol, dobletes de asistencias y gol+asistencia.
- [x] Aumentar numeros estadisticos, llevarlos a blanco y reducir grosor de barras.
- [x] Desaturar los colores comparativos manteniendo contraste AA.
- [x] Verificar teclado, foco, touch targets y `prefers-reduced-motion`.
- [x] Ejecutar pruebas backend enfocadas y completas.
- [x] Ejecutar `flake8`, `isort --check-only`, `git diff --check` y `npm run build`.
- [x] Verificar desktop y mobile con Playwright sin overflow ni solapamientos.

## Agent Routing Brief

**DDD Designer needed:** no

La feature agrega consultas de solo lectura y corrige composicion de datos existentes. No introduce
entidades persistentes, invariantes de negocio ni cambios al motor de scoring.

## Verificacion

1. Abrir `/torneos` y confirmar que selecciona la temporada de clubes mas reciente.
2. Cambiar de competicion y validar fechas, marcadores, tabla y cruces con la base local.
3. Abrir `/mundial` y confirmar redireccion a `/torneos`.
4. Comparar dos jugadores con partidos de multiples goles o asistencias y validar sus hitos.
5. Revisar barras y valores en 390x844, 768x1024 y 1440x1000.

Resultado: 542 pruebas backend y build de produccion frontend aprobados. Los flujos de Torneos y
Comparar se validaron con Playwright en escritorio y movil, sin overflow horizontal ni errores de
consola de la aplicacion.
