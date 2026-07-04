# 0037 - AI Ranking Explanations

## Contexto de negocio

SFA ya calcula un ranking contextual, pero para un usuario nuevo el producto puede sentirse como
una tabla con muchos numeros. La oportunidad de producto es convertir el Top 3/Top 10 en una
historia entendible: explicar por que un jugador esta arriba, con evidencia real del motor SFA.

La IA no decide el ranking ni inventa argumentos. El ranking sigue saliendo de
`sfa_season_scores`, `player_event_scores`, `player_stats`, logros y bonus. La IA solo redacta
texto a partir de un paquete de evidencia generado por backend y guardado en DB.

La primera experiencia visible sera:

- Carrusel mobile sobre el Top 3 del ranking, rotando cada 3 segundos.
- CTA "Ver analisis" con una explicacion mas larga.
- Perfil del jugador con analisis extendido si ese jugador pertenece al Top 10 cacheado.
- Fallback deterministico cuando no exista API key o falle el proveedor externo.

## Objetivos

- Explicar el Top 10 del ranking con lenguaje humano y datos trazables.
- Mostrar Top 3 en mobile como carrusel narrativo, no como bloque tecnico.
- Mostrar analisis extendido en perfil y en "Ver mas".
- Cachear resultados en DB para no llamar IA por cada visita.
- Funcionar sin API key con texto deterministico.
- Mantener arquitectura hexagonal: Router -> Use Case -> Repository/Provider.
- Disenar seguridad anti-hallucination: evidencia cerrada, salida JSON validada, fallback si el
  texto menciona datos fuera del paquete.

## No objetivos

- No cambiar el algoritmo de ranking.
- No cambiar puntos, multiplicadores ni scoring.
- No llamar a IA desde el navegador.
- No generar explicaciones para todos los jugadores en la primera version.
- No depender de IA para que la pagina funcione.
- No hacer streaming de texto.

## Codebase analizado

- `backend/CLAUDE.md`: arquitectura hexagonal, workflow de specs y reglas de testing.
- `backend/.claude/agents/Architecture-Engineer.md`: reglas del agente de arquitectura.
- `backend/src/sfa/domain/ports.py`: `RankedPlayerDTO`, `PlayerFixtureDTO`, repositorios actuales.
- `backend/src/sfa/application/use_cases/get_ranking.py`: resolucion de ranking y paginacion.
- `backend/src/sfa/api/v1/ranking.py`: contrato actual de `/ranking`.
- `backend/src/sfa/api/v1/schemas/ranking.py`: schemas de ranking.
- `backend/src/sfa/infrastructure/repositories/sfa_score_repository.py`: queries de ranking,
  breakdown, B1 y filtros.
- `backend/src/sfa/infrastructure/repositories/player_event_repository.py`: datos de fixtures
  y calculo de pases completados desde `passes_total * passes_accuracy / 100`.
- `backend/src/sfa/application/use_cases/run_full_recalculation.py`: lugar natural para disparar
  regeneracion despues de score + achievements + bonuses.
- `backend/src/sfa/tasks/run_full_recalculation_task.py`: task actual de recalc.
- `backend/src/sfa/core/config.py`: settings existentes para API keys y env vars.
- `backend/src/sfa/core/dependencies.py`: wiring central.
- `frontend/src/pages/RankingPage.tsx`: separa podio Top 3 y lista; lugar del carrusel.
- `frontend/src/pages/PlayerPage.tsx`: pagina de perfil; lugar del analisis extendido.
- `frontend/src/api/client.ts` y `frontend/src/types/index.ts`: punto de integracion frontend.

## Decisiones arquitectonicas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Crear un subdominio ligero `ranking_explanations` con DTOs, ports y repository propio | Agregar campos de texto directamente a `RankedPlayerDTO` | Evita inflar `/ranking`, permite cache, auditoria y regeneracion independiente. |
| Endpoint dedicado `GET /ranking/explanations` | Incluir explicaciones dentro de `/ranking` | El ranking debe seguir liviano y paginado. Las explicaciones se piden solo para Top 3/Top 10. |
| Endpoint dedicado `GET /players/{player_id}/explanation` | Reutilizar `/players/{id}` | El perfil actual ya carga varias fuentes; un endpoint separado evita romper el contrato existente. |
| Guardar explicaciones en DB | Redis-only o memoria | Necesitamos persistencia, auditoria de evidencia, versionado por reglas y no regenerar con cada deploy. |
| Provider externo opcional via port `RankingExplanationWriterPort` | Llamar OpenAI/Gemini directo desde use case | Mantiene hexagonal: application depende de port, infra implementa provider. |
| Fallback deterministico obligatorio | Error si no hay API key | El producto debe funcionar en local, staging y produccion sin bloquear el ranking. |
| IA redacta sobre `evidence_json`; no recibe libertad para decidir merito | Prompt libre "explica por que es top" | Reduce hallucination y preserva confianza del producto. |
| Regenerar tras recalc completo mediante task secundaria | Regenerar en cada request | Controla costo, evita latencia y mantiene experiencia rapida. |
| Generar Top 10 por scope `season + rules_version_id + competition_id + use_total` | Generar global unico por jugador | El lugar en ranking depende del scope. Un jugador puede tener argumentos distintos en Mundial, club o all-seasons. |
| Mantener textos en espanol en DB | Traducir en frontend | Publico objetivo principal habla espanol; el texto cacheado debe ser producto-ready. |

## Modelo de dominio propuesto

Este spec requiere DDD ligero porque introduce una entidad conceptual nueva:
`RankingPlayerExplanation`, con invariantes de evidencia y frescura.

### Entidad: RankingPlayerExplanation

Representa una explicacion narrativa cacheada para un jugador dentro de un ranking concreto.

Campos conceptuales:

- `id`
- `player_id`
- `season`
- `competition_id | null`
- `rules_version_id | null`
- `rank`
- `scope` (`ranking`, `world_cup`, `all`, futuro)
- `variant` (`ai`, `deterministic`)
- `status` (`generated`, `fallback`, `failed`, `stale`)
- `short_text`
- `long_text`
- `bullets`
- `evidence_json`
- `model_name | null`
- `prompt_version`
- `input_tokens | null`
- `output_tokens | null`
- `cost_estimate_usd | null`
- `source_hash`
- `generated_at`
- `expires_at | null`
- `error | null`

Invariantes:

- `short_text` no debe superar 280 caracteres para carrusel mobile.
- `long_text` no debe superar 1800 caracteres en v1.
- `evidence_json` es obligatorio incluso en fallback.
- `source_hash` identifica el paquete de evidencia; si cambia, la explicacion queda stale.
- Solo se sirve texto `generated` o `fallback`; `failed` no aparece en frontend.
- Una explicacion pertenece a un scope exacto. No se reutiliza entre Mundial y ranking global.

### Evidence package

El backend arma un paquete cerrado con datos reales:

- rank, total points, matches, position, team, competition.
- goals, assists, dribbles, duels, B1 bonus, achievement bonus.
- breakdown de puntos por tipo de accion desde `sfa_season_scores.breakdown`.
- eventos top por puntos desde `player_event_scores` + `player_events` + `fixtures`.
- rivales y dificultad: M1 promedio/top events, team strength si disponible.
- instancia: stage/fase de eventos destacados y logros.
- contexto temporal: minutos y marcador para eventos clave si existe.
- comparativa contra Top 10: diferencia de puntos, produccion por partido.

La IA solo recibe este JSON. Si una frase no puede justificarse con este JSON, no debe aparecer.

## Ports nuevos

Crear `src/sfa/domain/ranking_explanation_ports.py`.

### DTOs

- `RankingExplanationEvidenceDTO`
- `RankingPlayerExplanationDTO`
- `RankingExplanationRequestDTO`
- `RankingExplanationWriteResultDTO`
- `RankingExplanationGenerationSummaryDTO`

### Repository protocol

`RankingExplanationRepositoryProtocol`

Responsabilidades:

- Obtener Top N para un scope usando la misma semantica que ranking activo.
- Construir evidencia por jugador.
- Obtener explicaciones cacheadas por scope.
- Obtener explicacion de un jugador por scope.
- Upsert de explicaciones.
- Marcar stale por scope cuando cambia `source_hash`.
- Registrar errores de generacion.

### Provider port

`RankingExplanationWriterPort`

Responsabilidades:

- Recibir `RankingExplanationEvidenceDTO`.
- Devolver `short_text`, `long_text`, `bullets`, metadata de modelo/tokens/costo.
- No acceder a DB.

Implementaciones:

- `DeterministicRankingExplanationWriter`: siempre disponible, sin API key.
- `OpenAICompatibleRankingExplanationWriter`: opcional, activado por env vars.

## Modelo DB

Crear migracion nueva. El numero de spec es `0037`, pero ya existe
`migrations/0037_tune_defender_pass_control.sql`; por lo tanto la migracion propuesta debe usar
el siguiente numero disponible, esperado `0038_create_ranking_player_explanations.sql`.

Tabla: `ranking_player_explanations`

Columnas:

- `id SERIAL PRIMARY KEY`
- `player_id INTEGER NOT NULL REFERENCES players(id)`
- `season VARCHAR(10) NOT NULL`
- `competition_id INTEGER NULL REFERENCES competitions(id)`
- `rules_version_id INTEGER NULL REFERENCES scoring_rules_versions(id)`
- `scope VARCHAR(30) NOT NULL`
- `rank INTEGER NOT NULL`
- `variant VARCHAR(20) NOT NULL`
- `status VARCHAR(20) NOT NULL`
- `short_text TEXT NOT NULL`
- `long_text TEXT NOT NULL`
- `bullets JSONB NOT NULL DEFAULT '[]'`
- `evidence_json JSONB NOT NULL`
- `model_name VARCHAR(80) NULL`
- `prompt_version VARCHAR(30) NOT NULL`
- `input_tokens INTEGER NULL`
- `output_tokens INTEGER NULL`
- `cost_estimate_usd NUMERIC(10, 6) NULL`
- `source_hash VARCHAR(64) NOT NULL`
- `generated_at TIMESTAMPTZ NOT NULL`
- `expires_at TIMESTAMPTZ NULL`
- `error TEXT NULL`

Indices:

- Unique parcial/logico por `(player_id, season, competition_id, rules_version_id, scope)`.
- Index por `(season, competition_id, rules_version_id, scope, rank)`.
- Index por `(player_id, season, rules_version_id)`.
- Index por `status`.

Nota sobre `competition_id NULL`: PostgreSQL permite multiples NULL en unique. La implementacion
debe resolver esto con dos unique indexes parciales, uno para `competition_id IS NULL` y otro para
`competition_id IS NOT NULL`, como ya se hace en otras zonas del proyecto.

## Settings

Agregar en `Settings`:

- `AI_EXPLANATIONS_ENABLED: bool = False`
- `AI_EXPLANATIONS_PROVIDER: str = "deterministic"`
- `AI_EXPLANATIONS_API_KEY: str = ""`
- `AI_EXPLANATIONS_BASE_URL: str = ""`
- `AI_EXPLANATIONS_MODEL: str = "gpt-5-nano"` (configurable; no hardcodear proveedor)
- `AI_EXPLANATIONS_TIMEOUT_SECONDS: int = 20`
- `AI_EXPLANATIONS_TOP_N: int = 10`
- `AI_EXPLANATIONS_PROMPT_VERSION: str = "ranking-explanation-v1"`
- `AI_EXPLANATIONS_MAX_INPUT_TOKENS_PER_PLAYER: int = 1800`
- `AI_EXPLANATIONS_MAX_OUTPUT_TOKENS_PER_PLAYER: int = 700`
- `AI_EXPLANATIONS_DAILY_BUDGET_USD: float = 2.0`

Si `AI_EXPLANATIONS_ENABLED=false` o no hay API key, usar provider deterministico.

## Seguridad anti-hallucination

Reglas obligatorias:

- Prompt con instrucciones estrictas: usar solo evidencia provista.
- Salida JSON obligatoria con campos `short_text`, `long_text`, `bullets`, `used_evidence_keys`.
- Validar JSON con Pydantic en el adapter de infraestructura.
- Rechazar texto que mencione datos no presentes en `evidence_json` segun checks simples:
  - numeros no presentes en evidencia,
  - nombres de rivales no presentes,
  - fases no presentes,
  - palabras de certeza historica extrema como "nunca en la historia" salvo que exista una key
    explicita en evidencia.
- Si falla validacion: guardar `status=fallback`, `variant=deterministic`, `error`.
- No exponer prompts ni raw provider responses al frontend.
- Guardar `evidence_json` para auditoria interna.

## Estrategia de costos

Costo controlado por diseno:

- Generar solo Top 10 por scope.
- Generar post-recalculo o bajo endpoint admin/manual, nunca por visita.
- Cache DB: miles de lecturas no generan costo.
- Token budget por jugador:
  - input maximo: 1200-1800 tokens.
  - output maximo: 400-700 tokens.
- Top 10 por generacion: aprox 16k-25k tokens.
- Con modelos economicos, el costo esperado debe ser centavos por generacion. Antes de activar
  produccion se debe verificar pricing actual del proveedor elegido y ajustar
  `AI_EXPLANATIONS_DAILY_BUDGET_USD`.
- Registrar tokens y costo estimado por fila para auditoria.
- Si se supera presupuesto diario: provider vuelve a fallback deterministico y loguea warning.

## Regeneracion

Disparadores:

- Al terminar `run_full_recalculation_task` con status completed.
- Endpoint admin manual para regenerar un scope.
- Opcional: task programada diaria para refrescar si hay explicaciones stale.

Flujo recomendado:

1. `run_full_recalculation_task` completa scoring y bonus.
2. Hace commit de scoring.
3. Encola `generate_ranking_explanations_task`.
4. La task secundaria genera Top 10. Si falla, no revierte el recalc.

Esto evita que una caida del proveedor IA rompa el pipeline critico de puntos.

## Endpoints backend

### Publicos

- `GET /api/v1/ranking/explanations`
  - params: `season`, `competition_id`, `rules_version_id`, `scope`, `limit=10`.
  - respuesta: lista ordenada por rank con textos y metadata minima.

- `GET /api/v1/players/{player_id}/explanation`
  - params: `season`, `competition_id`, `rules_version_id`, `scope`.
  - respuesta: explicacion cacheada o `404` si no existe.

### Admin

- `POST /api/v1/admin/ranking-explanations/generate`
  - protegido por `require_admin_key`.
  - body: `season`, `competition_id`, `rules_version_id`, `scope`, `limit`, `force`.
  - respuesta: `task_id`.

## Celery

Task nueva:

- `generate_ranking_explanations_task`

Parametros:

- `season`
- `rules_version_id`
- `competition_id | None`
- `scope`
- `limit=10`
- `force=False`

Debe:

- resolver provider segun settings,
- construir evidencia,
- saltar filas cuyo `source_hash` no cambio salvo `force=True`,
- guardar AI o fallback,
- commitear por batch o al final,
- loguear resumen: generated, fallback, skipped, failed, estimated_cost.

## Frontend

### Ranking mobile Top 3

Crear componente:

- `TopRankingNarrativeCarousel`

Uso:

- Solo para Mundial/mobile inicialmente.
- Ubicado entre controles y podio en `RankingPage`.
- Toma `top3` y explicaciones cacheadas de `GET /ranking/explanations`.
- Rota cada 3 segundos.
- Pausa cuando usuario toca/hover/focus.
- Muestra:
  - rank,
  - jugador,
  - seleccion/equipo,
  - short_text,
  - CTA "Ver analisis".
- Si no hay explicacion: no rompe layout; puede mostrar skeleton o texto deterministico si backend
  lo devuelve.

### Ver mas

Componente:

- `RankingExplanationModal` o panel inline.

Debe mostrar:

- `long_text`.
- bullets.
- chips de evidencia: goles, asistencias, puntos, partidos, bonus, eventos clave.
- fecha de generacion.

### Perfil de jugador

En `PlayerPage`:

- llamar `fetchPlayerExplanation(playerId, season)`.
- mostrar bloque "Analisis SFA" bajo `PlayerHeader` o antes de `StatBar`.
- si no existe explicacion, ocultar el bloque.

## Observabilidad y rollback

Logs:

- `[GenerateRankingExplanationsUseCase]`
- `[generate_ranking_explanations_task]`
- `[OpenAICompatibleRankingExplanationWriter]`

Metricas DB:

- filas por status,
- costo estimado diario,
- porcentaje fallback,
- age de cache.

Rollback:

- Poner `AI_EXPLANATIONS_ENABLED=false`.
- El frontend sigue mostrando fallback cacheado u oculta bloques si endpoint falla.
- No afecta ranking ni scoring.

## DDD Brief

DDD Designer requerido: si.

Motivo:

- Se introduce una entidad de dominio nueva (`RankingPlayerExplanation`) con invariantes de
  evidencia, scope, freshness y estado.
- Se introduce un value concept (`EvidencePackage`/`source_hash`) que debe proteger que la IA no
  decida ranking ni argumente fuera de datos reales.

El DDD Designer debe validar:

1. Limites de la entidad: cache narrativo por scope, no parte del scoring.
2. Invariantes de `short_text`, `long_text`, `source_hash`, status y evidence.
3. Si `RankingExplanationEvidenceDTO` debe vivir en `domain/ranking_explanation_ports.py` o en
   un submodulo `domain/ranking_explanations/`.
4. Que el provider externo sea un port de salida y no contamine application/domain.
5. Que la regeneracion sea eventually consistent y no transaccional con el scoring.

## DDD Validation

Validado por `DDD-Designer` antes de implementar.

- `RankingPlayerExplanation` pertenece a un bounded context liviano `ranking_explanations`, no a
  `domain/scoring`, porque no modifica puntos, multiplicadores ni `BASE_POINTS_TABLE`.
- La ubicacion aprobada para v1 es `backend/src/sfa/domain/ranking_explanation_ports.py`.
- Estados publicos: solo `generated` y `fallback`. `failed` y `stale` son internos.
- `source_hash` es SHA-256 sobre evidencia canonica, no sobre el texto generado.
- `rank`, `total_pts`, `rules_version_id`, `use_total`, breakdown, B1, bonus de logros y eventos
  clave deben formar parte del material hasheado.
- La explicacion queda stale si el hash canonico nuevo difiere del guardado.
- La IA/proveedor externo solo redacta sobre `evidence_json`; la evidencia es la frontera de
  confianza.
