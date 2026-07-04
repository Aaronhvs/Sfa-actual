# Plan: 0037 - AI Ranking Explanations

## Fase 0 - DDD y contrato del dominio

- [x] [DDD] Revisar `decisions.md` y confirmar la entidad `RankingPlayerExplanation`, los estados
  permitidos y las invariantes de `source_hash`, evidence y textos.
  - Criterio: el DDD brief queda aceptado o ajustado antes de crear codigo.
- [x] [DDD] Definir ubicacion final de los DTOs y ports:
  `src/sfa/domain/ranking_explanation_ports.py` o subpaquete
  `src/sfa/domain/ranking_explanations/`.
  - Criterio: una sola ubicacion aprobada, sin duplicar DTOs.
- [x] [DDD] Definir reglas de stale:
  explicacion stale si cambia `source_hash`, `rank`, `total_pts`, `rules_version_id` o evidencia
  de eventos clave.
  - Criterio: regla escrita en comentario/docstring del use case correspondiente.

## Fase 1 - Persistencia

- [ ] Crear migracion `backend/migrations/0038_create_ranking_player_explanations.sql`
  o el siguiente numero disponible si 0038 ya existe.
  - Criterio: tabla `ranking_player_explanations` creada con columnas, constraints e indices
    definidos en `decisions.md`.
- [ ] Crear modelo SQLAlchemy en
  `src/sfa/infrastructure/models/ranking_explanations/models.py`.
  - Criterio: modelo importa `Base`, usa JSONB para `bullets` y `evidence_json`, y no rompe
    imports de modelos existentes.
- [ ] Exportar el modelo desde `src/sfa/infrastructure/models/ranking_explanations/__init__.py`
  y revisar si `models/__init__.py` necesita import.
  - Criterio: `python -m compileall src/sfa/infrastructure/models` pasa.

## Fase 2 - Domain ports y DTOs

- [ ] Crear `RankingExplanationEvidenceDTO`, `RankingPlayerExplanationDTO`,
  `RankingExplanationRequestDTO`, `RankingExplanationWriteResultDTO` y
  `RankingExplanationGenerationSummaryDTO`.
  - Criterio: dataclasses frozen, sin imports de infraestructura.
- [ ] Crear `RankingExplanationRepositoryProtocol`.
  - Criterio: protocol cubre top players, evidence, cache reads, upsert, stale y error logging.
- [ ] Crear `RankingExplanationWriterPort`.
  - Criterio: provider port acepta evidence y devuelve resultado estructurado; domain no importa
    httpx ni SDKs externos.

## Fase 3 - Repository

- [ ] Crear `src/sfa/infrastructure/repositories/ranking_explanation_repository.py`.
  - Criterio: implementa completo `RankingExplanationRepositoryProtocol`.
- [ ] Implementar query para obtener Top N por scope reutilizando la semantica real de ranking:
  `season`, `competition_id`, `rules_version_id`, `use_total=True` para Mundial si corresponde.
  - Criterio: Top 10 coincide con `/ranking` para el mismo scope.
- [ ] Implementar construccion de evidence por jugador.
  - Criterio: evidence incluye totales, breakdown, B1, achievement bonus, eventos top, fixtures,
    M1/M2/M3/Mvisit, rivales y comparativa basica contra Top 10.
- [ ] Implementar `source_hash` deterministico sobre evidence normalizada.
  - Criterio: mismo evidence produce mismo hash; cambio de puntos/eventos produce hash distinto.
- [ ] Implementar lecturas cacheadas por scope y por jugador.
  - Criterio: no retorna filas `failed`; ordena por `rank ASC`.
- [ ] Implementar upsert con partial unique indexes para `competition_id IS NULL` y
  `competition_id IS NOT NULL`.
  - Criterio: regenerar el mismo scope actualiza fila, no duplica.

## Fase 4 - Writers / Providers

- [ ] Crear `DeterministicRankingExplanationWriter`.
  - Criterio: genera `short_text`, `long_text` y bullets usando solo evidence; no requiere API key.
- [ ] Crear `OpenAICompatibleRankingExplanationWriter` en `infrastructure/providers/`.
  - Criterio: usa `httpx.AsyncClient`, base URL/model/api key desde settings, timeout configurable.
- [ ] Validar salida JSON del provider externo con Pydantic o DTO parser interno.
  - Criterio: JSON invalido activa fallback deterministico.
- [ ] Implementar guard anti-hallucination simple.
  - Criterio: si el texto contiene numeros/rivales/fases no presentes en evidence, se rechaza y
    se guarda fallback.
- [ ] Implementar budget guard diario.
  - Criterio: si costo estimado del dia supera `AI_EXPLANATIONS_DAILY_BUDGET_USD`, el provider
    usa fallback y loguea warning.

## Fase 5 - Use cases

- [ ] Crear `GenerateRankingExplanationsUseCase`.
  - Criterio: recibe repository + writer, genera hasta Top N, salta hash igual salvo `force=True`,
    retorna summary.
- [ ] Crear `GetRankingExplanationsUseCase`.
  - Criterio: retorna lista cacheada para ranking/carrusel sin generar en request.
- [ ] Crear `GetPlayerRankingExplanationUseCase`.
  - Criterio: retorna explicacion cacheada del jugador para el scope o `None`.
- [ ] Asegurar que errores del writer no rompen el use case completo.
  - Criterio: un jugador con fallo guarda fallback/error y los demas siguen.

## Fase 6 - Celery

- [ ] Crear `src/sfa/tasks/generate_ranking_explanations_task.py`.
  - Criterio: task sync -> async wrapper, late imports, session commit/rollback correcto.
- [ ] Registrar la task en `src/sfa/tasks/__init__.py`.
  - Criterio: worker lista `sfa.tasks.generate_ranking_explanations_task`.
- [ ] Modificar `run_full_recalculation_task` para encolar la task secundaria solo si recalc
  termino `completed`.
  - Criterio: falla de explicaciones no revierte scoring; logs muestran task secundaria.
- [ ] Parametrizar scope inicial:
  - Mundial: `season=2026`, `competition_id=350`, `scope=world_cup`.
  - Global/club: `competition_id=None`, `scope=ranking`.
  - Criterio: task puede ejecutarse manualmente para ambos casos.

## Fase 7 - Settings y wiring

- [ ] Agregar settings `AI_EXPLANATIONS_*` en `src/sfa/core/config.py`.
  - Criterio: defaults seguros, sin API key requerida.
- [ ] Agregar factory de repository en `core/dependencies.py`.
  - Criterio: wiring vive solo en dependencies.
- [ ] Agregar factory de writer provider en `core/dependencies.py` o helper dedicado llamado desde
  dependencies/tasks.
  - Criterio: provider deterministico cuando `AI_EXPLANATIONS_ENABLED=false` o key vacia.
- [ ] Agregar factories de use cases publicos.
  - Criterio: routers no instancian use cases directamente.

## Fase 8 - API

- [ ] Crear schemas en `src/sfa/api/v1/schemas/ranking_explanations.py`.
  - Criterio: schemas no exponen prompt ni errores internos por defecto.
- [ ] Crear router publico `src/sfa/api/v1/ranking_explanations.py`.
  - Criterio: endpoints `GET /ranking/explanations` y
    `GET /players/{player_id}/explanation` funcionan por use case.
- [ ] Registrar router en app principal donde se registran routers v1.
  - Criterio: endpoints aparecen en OpenAPI.
- [ ] Agregar endpoint admin `POST /admin/ranking-explanations/generate`.
  - Criterio: protegido con `require_admin_key`, retorna `task_id`.
- [ ] Crear archivo HTTP `backend/http/ranking_explanations.http`.
  - Criterio: incluye happy path, sin cache, player no top10, admin generate y caso sin API key.

## Fase 9 - Frontend API y tipos

- [ ] Agregar tipos `RankingPlayerExplanation`, `RankingExplanationsResponse` y
  `PlayerExplanationResponse` en `frontend/src/types/index.ts`.
  - Criterio: nombres y campos coinciden con schemas backend.
- [ ] Agregar `fetchRankingExplanations` y `fetchPlayerExplanation` en
  `frontend/src/api/client.ts`.
  - Criterio: usan cache liviana existente y aceptan season/competition/rules_version/scope.

## Fase 10 - Frontend mobile carousel Top 3

- [ ] Crear `frontend/src/components/ranking/TopRankingNarrativeCarousel.tsx`.
  - Criterio: rota cada 3 segundos entre Top 3, pausa en hover/focus/touch, accesible con
    `aria-live` prudente o controles manuales.
- [ ] Crear estilos responsive para mobile.
  - Criterio: visible en mobile sobre podio, no tapa controles, no genera layout shift fuerte.
- [ ] Integrar en `RankingPage` solo cuando `isWcSeason`, `page===0`, sin busqueda y top3 existe.
  - Criterio: desktop no cambia salvo decision explicita posterior.
- [ ] Agregar CTA "Ver analisis".
  - Criterio: abre modal/panel con long_text y bullets.
- [ ] Fallback UI.
  - Criterio: si endpoint falla, el ranking sigue igual y no aparece error visible grande.

## Fase 11 - Frontend perfil

- [ ] En `PlayerPage`, cargar explicacion del jugador para la season actual.
  - Criterio: no bloquea `PlayerHeader`, se puede cargar en paralelo.
- [ ] Crear bloque `PlayerNarrativeAnalysis`.
  - Criterio: muestra long_text, bullets y chips de evidencia.
- [ ] Ocultar bloque si no existe explicacion.
  - Criterio: jugadores fuera Top 10 no ven espacio vacio.

## Fase 12 - Tests backend

- [ ] Tests de `GenerateRankingExplanationsUseCase` con FakeRepository y FakeWriter.
  - Criterio: genera Top 10, usa fallback en error, salta hash igual, respeta force.
- [ ] Tests de `GetRankingExplanationsUseCase`.
  - Criterio: no retorna failed, respeta scope y orden.
- [ ] Tests de `GetPlayerRankingExplanationUseCase`.
  - Criterio: retorna DTO o None.
- [ ] Tests de guard anti-hallucination.
  - Criterio: numeros/rivales fuera de evidence disparan fallback.
- [ ] Tests de router con dependency override si existe patron local.
  - Criterio: schemas y status codes correctos.

## Fase 13 - Verificacion local

- [ ] Ejecutar `python -m compileall backend/src/sfa`.
  - Criterio: compila sin errores.
- [ ] Ejecutar tests use case relevantes.
  - Criterio: nuevos tests pasan; deuda preexistente documentada si impide suite global.
- [ ] Ejecutar `git diff --check`.
  - Criterio: sin whitespace errors.
- [ ] Ejecutar `npm run build` en frontend.
  - Criterio: build exitoso.

## Fase 14 - Rollout

- [ ] Aplicar migracion en staging/VPS.
  - Criterio: tabla existe e indices estan creados.
- [ ] Deploy con `AI_EXPLANATIONS_ENABLED=false`.
  - Criterio: fallback deterministico genera Top 10.
- [ ] Ejecutar admin generate para Mundial.
  - Criterio: 10 filas `fallback` o `generated`, ninguna `failed` visible.
- [ ] Activar provider externo con API key en entorno controlado.
  - Criterio: logs muestran tokens/costo; textos pasan validacion.
- [ ] Smoke test frontend mobile.
  - Criterio: carrusel Top 3 rota, CTA abre analisis, perfil Top 10 muestra bloque.
- [ ] Rollback documentado.
  - Criterio: `AI_EXPLANATIONS_ENABLED=false` desactiva IA sin tocar scoring.

## Archivos a crear

- `backend/specs/feature/0037-ai-ranking-explanations/decisions.md`
- `backend/specs/feature/0037-ai-ranking-explanations/plan.md`
- `backend/migrations/0038_create_ranking_player_explanations.sql`
- `backend/src/sfa/domain/ranking_explanation_ports.py`
- `backend/src/sfa/infrastructure/models/ranking_explanations/__init__.py`
- `backend/src/sfa/infrastructure/models/ranking_explanations/models.py`
- `backend/src/sfa/infrastructure/repositories/ranking_explanation_repository.py`
- `backend/src/sfa/infrastructure/providers/ranking_explanation_writer.py`
- `backend/src/sfa/application/use_cases/generate_ranking_explanations.py`
- `backend/src/sfa/application/use_cases/get_ranking_explanations.py`
- `backend/src/sfa/application/use_cases/get_player_ranking_explanation.py`
- `backend/src/sfa/tasks/generate_ranking_explanations_task.py`
- `backend/src/sfa/api/v1/schemas/ranking_explanations.py`
- `backend/src/sfa/api/v1/ranking_explanations.py`
- `backend/http/ranking_explanations.http`
- `backend/tests/use_cases/test_generate_ranking_explanations.py`
- `backend/tests/use_cases/test_get_ranking_explanations.py`
- `backend/tests/use_cases/test_get_player_ranking_explanation.py`
- `frontend/src/components/ranking/TopRankingNarrativeCarousel.tsx`
- `frontend/src/components/player/PlayerNarrativeAnalysis.tsx`

## Archivos a modificar

- `backend/src/sfa/core/config.py`
- `backend/src/sfa/core/dependencies.py`
- `backend/src/sfa/tasks/__init__.py`
- `backend/src/sfa/tasks/run_full_recalculation_task.py`
- `backend/src/sfa/api/v1/__init__.py` o archivo donde se registren routers
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/RankingPage.tsx`
- `frontend/src/pages/PlayerPage.tsx`
- CSS global o modulo existente de ranking/player.

## Agent Routing Brief

**DDD Designer needed:** yes

Items:

- Fase 0 completa.
- Fase 2 DTO/ports si el DDD Designer decide crear subpaquete de dominio.
- Fase 4 anti-hallucination guard si se modela como domain service puro.

Brief:

La feature introduce una entidad nueva, `RankingPlayerExplanation`, que no modifica scoring pero
si define un cache narrativo con reglas de consistencia. El DDD Designer debe validar:

1. La entidad pertenece a un subdominio de explicabilidad/narrativa, no al subdominio scoring.
2. `EvidencePackage` y `source_hash` son la frontera de confianza: la IA solo redacta sobre
   evidencia.
3. Los estados `generated`, `fallback`, `failed`, `stale` son suficientes.
4. La consistencia es eventual: scoring no se revierte si falla la generacion narrativa.
5. El fallback deterministico es parte del dominio de producto, no solo manejo de error tecnico.
