# Plan: Explicaciones contextuales del Top 3

## Estado de ejecucion (2026-08-08)

Implementado el Top 3 contextual para award periods, temporadas y torneos, incluyendo filtros
de competicion, posicion y perfil. El cache editorial se valida contra jugadores, puestos y
puntos actuales; si falta o esta stale se construye un fallback determinista no persistido.

Verificacion: 11 pruebas enfocadas pasan; suite completa 442 aprobadas y 2 fallos historicos no
relacionados en `ShootoutDecider`; flake8, isort, TypeScript, import de API y build Vite pasan.

## Archivos a crear

- [ ] `backend/tests/use_cases/test_get_contextual_ranking_explanations.py` - cache y fallback por scope/filtros.

## Archivos a modificar

- [ ] `backend/src/sfa/domain/ranking_explanation_ports.py` - contexto canonico y contrato de evidencia por scope.
- [ ] `backend/src/sfa/application/use_cases/generate_ranking_explanations.py` - ranking compuesto para generacion editorial.
- [ ] `backend/src/sfa/application/use_cases/get_ranking_explanations.py` - fallback determinista contextual.
- [ ] `backend/src/sfa/infrastructure/repositories/ranking_explanation_repository.py` - filtros multi-source para evidencia.
- [ ] `backend/src/sfa/infrastructure/providers/ranking_explanation_writer.py` - lenguaje de temporada/competicion visible.
- [ ] `backend/src/sfa/api/v1/schemas/ranking_explanations.py` - aceptar scope y filtros canonicos.
- [ ] `backend/src/sfa/api/v1/ranking_explanations.py` - propagar contexto sin resolverlo en router.
- [ ] `backend/src/sfa/core/dependencies.py` - wiring del use case contextual.
- [ ] `backend/src/sfa/tasks/generate_ranking_explanations_task.py` - scope key para jobs editoriales.
- [ ] `backend/src/sfa/tasks/recalculate_award_period_task.py` - encolar Top 3 global al finalizar.
- [ ] `frontend/src/api/client.ts` - enviar scope key, posicion y perfil.
- [ ] `frontend/src/pages/RankingPage.tsx` - habilitar carrusel en todas las vistas Top 3.

## Checklist de implementacion

- [ ] Agregar filtros opcionales con defaults compatibles al request DTO.
- [ ] Resolver `AwardPeriodScope` y version comun antes de obtener ranking.
- [ ] Aplicar competition, position y bonus label tanto al ranking como al contexto narrativo.
- [ ] Filtrar score rows, stats, eventos y partidos por todos los pares del scope.
- [ ] Incluir label y filtros visibles en el JSON de evidencia.
- [ ] Reutilizar cache solo en contextos sin filtros no representados por su clave persistida.
- [ ] Construir tres DTOs deterministas no persistidos cuando falte cache.
- [ ] Mantener compatibilidad de endpoints y tasks existentes del Mundial.
- [ ] Encolar generacion `award_period` global despues de un recalculo exitoso.
- [ ] Mostrar el carrusel para cualquier season en pagina 1 y sin busqueda.
- [ ] Vaciar explicaciones al cambiar contexto y evitar mostrar texto anterior durante la carga.
- [ ] Probar temporada regular, Mundial, award period compuesto, Champions y posicion.
- [ ] Verificar `pytest`, flake8, isort, TypeScript y build Vite.

## Agent Routing Brief

**DDD Designer needed:** no

La feature no cambia scoring ni modela un concepto futbolistico nuevo. Extiende contratos read-side
y orquesta value objects de scope ya existentes.

## Verificacion

1. `season-2025` muestra explicaciones cuyo total/evidencia suma clubes 2025 y Mundial 2026.
2. Al filtrar Champions, los tres textos corresponden al Top 3 de esa competicion.
3. Al filtrar posicion o perfil, no aparece cache del ranking global.
4. Mundial conserva sus explicaciones cacheadas existentes.
5. Una temporada sin cache devuelve tres fallbacks deterministas y no llama al provider externo.
