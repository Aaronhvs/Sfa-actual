# 0005 — Sofascore: foto y heatmap — Plan de implementación

## TL;DR

Integrar Sofascore como tercera fuente de enrichment para foto y heatmap de jugadores.
Flujo en dos fases (Fase A: resolve `sofascore_id` + foto / Fase B: fetch heatmap) con dos
use cases, un provider HTTP, un repository dedicado, dos Celery tasks y tres endpoints admin.
El campo `heatmap_url` se expone en `GET /players/{id}`. Sin nueva entidad de dominio.

---

## Archivos a modificar

- [ ] `src/sfa/infrastructure/models/players/models.py` — añadir columna `heatmap_url`
- [ ] `src/sfa/domain/enrichment_ports.py` — nuevos DTOs y Protocols de Sofascore
- [ ] `src/sfa/domain/ports.py` — añadir `heatmap_url` a `PlayerDTO` y `PlayerScoreDTO`
- [ ] `src/sfa/infrastructure/repositories/__init__.py` — exportar `SofascoreEnrichmentRepository`
- [ ] `src/sfa/infrastructure/repositories/player_repository.py` — incluir `heatmap_url` en SELECT y DTO
- [ ] `src/sfa/infrastructure/repositories/sfa_score_repository.py` — JOIN con `players.heatmap_url` en `get_best_score_for_player_season`
- [ ] `src/sfa/application/use_cases/get_player_detail.py` — añadir `heatmap_url` a `PlayerDetailResult` y propagarlo desde `score.heatmap_url`
- [ ] `src/sfa/api/v1/schemas/players.py` — añadir `heatmap_url: str | None = None` al schema de detalle
- [ ] `src/sfa/api/v1/admin.py` — tres endpoints admin nuevos de Sofascore
- [ ] `src/sfa/core/dependencies.py` — wiring de provider, repository y use cases de Sofascore

## Archivos a crear

- [ ] `src/sfa/infrastructure/providers/sofascore_provider.py` — `SofascoreProvider`
- [ ] `src/sfa/infrastructure/repositories/sofascore_enrichment_repository.py` — `SofascoreEnrichmentRepository`
- [ ] `src/sfa/application/use_cases/enrich_sofascore_photo.py` — `EnrichSofascorePhotoUseCase`
- [ ] `src/sfa/application/use_cases/fetch_sofascore_heatmap.py` — `FetchSofascoreHeatmapUseCase`
- [ ] `src/sfa/tasks/sofascore_tasks.py` — `enrich_sofascore_photo_task` + `fetch_sofascore_heatmap_task`
- [ ] `tests/use_cases/test_enrich_sofascore_photo.py`
- [ ] `tests/use_cases/test_fetch_sofascore_heatmap.py`
- [ ] `http/sofascore.http` — happy path + error cases de los 3 endpoints admin nuevos

---

## Checklist de implementación

Procesar en orden estricto. Cada task debe completarse y verificarse antes de avanzar.

---

### Task 1 — Migration SQL

**Contexto:** `sofascore_id` existe en el modelo SQLAlchemy pero su DDL está pendiente.
`heatmap_url` es una columna nueva en ambos lados (modelo y DB).

- [ ] Verificar el estado actual de la tabla ejecutando:
  `SELECT column_name FROM information_schema.columns WHERE table_name = 'players' ORDER BY ordinal_position;`
- [ ] Ejecutar el siguiente SQL (idempotente con `IF NOT EXISTS`):
  ```sql
  ALTER TABLE players ADD COLUMN IF NOT EXISTS sofascore_id INTEGER UNIQUE;
  ALTER TABLE players ADD COLUMN IF NOT EXISTS heatmap_url TEXT;
  ```
- [ ] Verificar resultado: la query de `information_schema` incluye `sofascore_id` y `heatmap_url`
- [ ] Actualizar el comentario de migrations en `src/sfa/infrastructure/models/players/models.py`
  para reflejar ambas columnas como aplicadas

---

### Task 2 — Añadir `heatmap_url` al modelo SQLAlchemy

**Archivo:** `src/sfa/infrastructure/models/players/models.py`

- [ ] Confirmar que `from __future__ import annotations` NO está en el archivo
  (los modelos SQLAlchemy 2.0 con `Mapped[]` no lo usan — su presencia rompe el typing de columnas)
- [ ] Añadir al final de la clase `Player`, después de `sofascore_id`:
  `heatmap_url: Mapped[str | None] = mapped_column(Text, nullable=True)`
- [ ] Criterio de completitud: `python -c "from sfa.infrastructure.models.players.models import Player; assert hasattr(Player, 'heatmap_url')"` no lanza error

---

### Task 3 — Nuevos DTOs y Protocols en `domain/enrichment_ports.py`

**Archivo:** `src/sfa/domain/enrichment_ports.py`

- [ ] Confirmar que `from __future__ import annotations` está en la primera línea
- [ ] En la sección **Raw DTOs**, añadir frozen dataclass `SofascorePlayerDTO`:
  - `sofascore_id: int`
  - `name: str`
- [ ] En la sección **Internal row DTOs**, añadir frozen dataclass `SofascorePlayerRow`:
  - `id: int`
  - `name: str`
  - `sofascore_id: int | None`
- [ ] En la sección **Result DTOs**, añadir frozen dataclass `SofascoreEnrichmentResult`:
  - `player_id: int`
  - `sofascore_id: int | None`
  - `photo_url: str | None`
  - `heatmap_url: str | None`
  - `status: str`
  - `error: str | None`
- [ ] Al final de la sección **Ports**, añadir `@runtime_checkable` Protocol `SofascoreProviderPort`:
  - `async def search_player(self, name: str) -> SofascorePlayerDTO | None: ...`
  - `def get_heatmap_url(self, sofascore_id: int, unique_tournament_id: int, season_id: int) -> str: ...`
  - Nota: `get_heatmap_url` es síncrono — solo construye un string, no hace I/O
- [ ] Al final de la sección **Ports**, añadir `@runtime_checkable` Protocol `SofascoreEnrichmentRepositoryPort`:
  - `async def get_player_for_sofascore(self, player_id: int) -> SofascorePlayerRow | None: ...`
  - `async def update_player_sofascore_id(self, player_id: int, sofascore_id: int) -> None: ...`
  - `async def update_player_photo_url(self, player_id: int, photo_url: str) -> None: ...`
  - `async def update_player_heatmap_url(self, player_id: int, heatmap_url: str) -> None: ...`
- [ ] Criterio: `from sfa.domain.enrichment_ports import SofascoreProviderPort, SofascoreEnrichmentRepositoryPort, SofascorePlayerDTO, SofascorePlayerRow, SofascoreEnrichmentResult` no lanza error

---

### Task 4 — Ampliar DTOs de lectura en `domain/ports.py`

**Archivo:** `src/sfa/domain/ports.py`

- [ ] En `PlayerDTO`, añadir campo al final con default: `heatmap_url: str | None = None`
- [ ] En `PlayerScoreDTO`, añadir campo al final con default: `heatmap_url: str | None = None`
- [ ] Criterio: `pytest tests/` pasa sin regresiones — los call sites existentes que construyen
  estos DTOs sin `heatmap_url` no se rompen gracias al default `None`

---

### Task 5 — Implementar `SofascoreProvider`

**Archivo:** `src/sfa/infrastructure/providers/sofascore_provider.py`

- [ ] `from __future__ import annotations` en la primera línea
- [ ] Imports: `difflib`, `logging`, `httpx`, y los DTOs de `sfa.domain.enrichment_ports`
- [ ] Constantes de clase:
  - `_SEARCH_BASE = "https://api.sofascore.com/api/v1"`
  - `_IMG_BASE = "https://img.sofascore.com/api/v1"`
  - `_MATCH_THRESHOLD = 0.75`
  - `_HEADERS` con User-Agent estándar de navegador (igual que los otros providers)
- [ ] Método `async def search_player(self, name: str) -> SofascorePlayerDTO | None`:
  - GET `{_SEARCH_BASE}/search/multi-search?q={name}` con `httpx.AsyncClient`
  - Timeout 20s; en caso de `HTTPStatusError` o `RequestError`: 2 reintentos con `asyncio.sleep(10)` entre intentos
  - Parsear clave `"results"` del JSON; para cada resultado donde `result["type"] == "player"`,
    extraer `result["entity"]["id"]` y `result["entity"]["name"]`
  - Calcular `difflib.SequenceMatcher(None, name.lower(), entity_name.lower()).ratio()`
  - Retornar `SofascorePlayerDTO` del primer resultado con ratio >= `_MATCH_THRESHOLD`
  - Si ningún resultado supera el umbral: log `WARNING "[SofascoreProvider] No match for '{name}'"` y retornar `None`
  - Si match encontrado: log `INFO "[SofascoreProvider] Matched '{name}' → '{entity_name}' (ratio={ratio:.2f})"`
- [ ] Método `def get_heatmap_url(self, sofascore_id: int, unique_tournament_id: int, season_id: int) -> str`:
  - Retorna `f"{_SEARCH_BASE}/player/{sofascore_id}/heatmap/{unique_tournament_id}/{season_id}"`
  - Síncrono puro — sin I/O
- [ ] Método privado `def _build_photo_url(self, sofascore_id: int) -> str`:
  - Retorna `f"{_IMG_BASE}/player/{sofascore_id}/image"`
- [ ] Verificar conformidad con el Protocol:
  `assert isinstance(SofascoreProvider(), SofascoreProviderPort)`

---

### Task 6 — Implementar `SofascoreEnrichmentRepository`

**Archivo:** `src/sfa/infrastructure/repositories/sofascore_enrichment_repository.py`

- [ ] `from __future__ import annotations` en la primera línea
- [ ] Imports: `select`, `update` de `sqlalchemy`; `AsyncSession`; `Player` model; DTOs del domain
- [ ] Clase `SofascoreEnrichmentRepository` que satisfaga `SofascoreEnrichmentRepositoryPort`
- [ ] Constructor: `def __init__(self, session: AsyncSession) -> None`
- [ ] Método `get_player_for_sofascore`:
  - `SELECT Player.id, Player.name, Player.sofascore_id WHERE Player.id == player_id`
  - Retorna `SofascorePlayerRow` o `None`
- [ ] Método `update_player_sofascore_id`:
  - `UPDATE players SET sofascore_id=... WHERE id=player_id AND sofascore_id IS NULL`
  - La condición `IS NULL` protege IDs verificados manualmente
  - Llamar `await self._session.flush()`
- [ ] Método `update_player_photo_url`:
  - `UPDATE players SET photo_url=... WHERE id=player_id`
  - Llamar `await self._session.flush()`
- [ ] Método `update_player_heatmap_url`:
  - `UPDATE players SET heatmap_url=... WHERE id=player_id`
  - Llamar `await self._session.flush()`
- [ ] Añadir `SofascoreEnrichmentRepository` a `src/sfa/infrastructure/repositories/__init__.py`
- [ ] Verificar conformidad: `assert isinstance(SofascoreEnrichmentRepository(session), SofascoreEnrichmentRepositoryPort)`

---

### Task 7 — Implementar `EnrichSofascorePhotoUseCase`

**Archivo:** `src/sfa/application/use_cases/enrich_sofascore_photo.py`

- [ ] `from __future__ import annotations` en la primera línea
- [ ] Importar solo desde `sfa.domain.enrichment_ports` — cero imports de `infrastructure/`
- [ ] Añadir Protocol `EnrichSofascorePhotoUseCaseProtocol` (`@runtime_checkable`):
  - `async def execute(self, player_id: int) -> SofascoreEnrichmentResult: ...`
- [ ] Clase `EnrichSofascorePhotoUseCase`:
  - Constructor: `__init__(self, provider: SofascoreProviderPort, repo: SofascoreEnrichmentRepositoryPort)`
  - Método `async def execute(self, player_id: int) -> SofascoreEnrichmentResult` con la lógica:
    1. `row = await self._repo.get_player_for_sofascore(player_id)`
       Si `row is None` → retornar result `status="failed"`, `error="Player {player_id} not found"`
    2. Si `row.sofascore_id is not None`: usar `sofascore_id = row.sofascore_id` directamente (skip search)
       Si `row.sofascore_id is None`: `match = await self._provider.search_player(row.name)`
       Si `match is None` → retornar result `status="failed"`, `error="No Sofascore match found for '{row.name}'"`
       `sofascore_id = match.sofascore_id`
    3. Si `row.sofascore_id is None`: `await self._repo.update_player_sofascore_id(player_id, sofascore_id)`
    4. `photo_url = f"https://img.sofascore.com/api/v1/player/{sofascore_id}/image"`
    5. `await self._repo.update_player_photo_url(player_id, photo_url)`
    6. Retornar `SofascoreEnrichmentResult(player_id=player_id, sofascore_id=sofascore_id, photo_url=photo_url, heatmap_url=None, status="completed", error=None)`
  - Capturar `Exception` genérica → log `ERROR "[EnrichSofascorePhotoUseCase] ..."` → retornar result `status="failed"`, `error=str(exc)`
- [ ] Logger con prefijo `[EnrichSofascorePhotoUseCase]`
- [ ] Criterio: el use case no importa nada de `infrastructure/`

---

### Task 8 — Implementar `FetchSofascoreHeatmapUseCase`

**Archivo:** `src/sfa/application/use_cases/fetch_sofascore_heatmap.py`

- [ ] `from __future__ import annotations` en la primera línea
- [ ] Importar solo desde `sfa.domain.enrichment_ports` — cero imports de `infrastructure/`
- [ ] Añadir Protocol `FetchSofascoreHeatmapUseCaseProtocol` (`@runtime_checkable`):
  - `async def execute(self, player_id: int, unique_tournament_id: int, season_id: int) -> SofascoreEnrichmentResult: ...`
- [ ] Clase `FetchSofascoreHeatmapUseCase`:
  - Constructor: `__init__(self, provider: SofascoreProviderPort, repo: SofascoreEnrichmentRepositoryPort)`
  - Método `async def execute(self, player_id: int, unique_tournament_id: int, season_id: int) -> SofascoreEnrichmentResult` con la lógica:
    1. `row = await self._repo.get_player_for_sofascore(player_id)`
       Si `row is None` → retornar result `status="failed"`, `error="Player {player_id} not found"`
    2. Si `row.sofascore_id is None` → retornar result `status="failed"`, `error="Player {player_id} has no sofascore_id — run enrich-photo first"`
    3. `heatmap_url = self._provider.get_heatmap_url(row.sofascore_id, unique_tournament_id, season_id)`
    4. `await self._repo.update_player_heatmap_url(player_id, heatmap_url)`
    5. Retornar `SofascoreEnrichmentResult(player_id=player_id, sofascore_id=row.sofascore_id, photo_url=None, heatmap_url=heatmap_url, status="completed", error=None)`
  - Capturar `Exception` genérica → log `ERROR "[FetchSofascoreHeatmapUseCase] ..."` → retornar result `status="failed"`, `error=str(exc)`
- [ ] Logger con prefijo `[FetchSofascoreHeatmapUseCase]`

---

### Task 9 — Exponer `heatmap_url` en `GET /players/{id}`

Esta task modifica la cadena de lectura: `SFAScoreRepository` → `PlayerScoreDTO` →
`GetPlayerDetailUseCase` → `PlayerDetailResult` → schema → respuesta HTTP.

**Archivos:** `domain/ports.py` (ya modificado en Task 4), `sfa_score_repository.py`,
`get_player_detail.py`, `api/v1/schemas/players.py`, `player_repository.py`

- [ ] En `src/sfa/infrastructure/repositories/sfa_score_repository.py`, método `get_best_score_for_player_season`:
  - Añadir `Player.heatmap_url` al SELECT (requiere que `Player` ya esté en el JOIN — verificar si existe)
  - Incluir `heatmap_url=row["heatmap_url"]` en la construcción del `PlayerScoreDTO`
  - Verificar que el JOIN con `Player` ya existe en la query; si no, añadirlo

- [ ] En `src/sfa/application/use_cases/get_player_detail.py`:
  - Añadir `heatmap_url: str | None = None` al frozen dataclass `PlayerDetailResult` (al final, con default)
  - En `execute()`, en la construcción del `PlayerDetailResult`, añadir `heatmap_url=score.heatmap_url`

- [ ] En `src/sfa/api/v1/schemas/players.py`:
  - Añadir `heatmap_url: str | None = None` al schema de detalle de jugador (buscar el schema que mapea `PlayerDetailResult`)

- [ ] En `src/sfa/infrastructure/repositories/player_repository.py`:
  - Añadir `Player.heatmap_url` al SELECT de `get_by_id`
  - Incluir `heatmap_url=row["heatmap_url"]` en la construcción del `PlayerDTO`

- [ ] Criterio: `GET /players/{id}` incluye el campo `heatmap_url` con valor `null` para jugadores sin heatmap procesado

---

### Task 10 — Celery tasks en `tasks/sofascore_tasks.py`

**Archivo:** `src/sfa/tasks/sofascore_tasks.py`

- [ ] Crear archivo siguiendo el patrón de `enrichment_tasks.py` (imports locales dentro del helper async)
- [ ] `import asyncio` y `from sfa.celery_app import celery_app`
- [ ] Task `enrich_sofascore_photo_task`:
  - `@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)`
  - Firma: `def enrich_sofascore_photo_task(self, player_id: int)`
  - Body: `asyncio.run(_run_enrich_sofascore_photo(player_id))` dentro de try/except → `raise self.retry(exc=exc)`
- [ ] Helper async `_run_enrich_sofascore_photo(player_id: int)`:
  - Importar localmente: `EnrichSofascorePhotoUseCase`, `SofascoreProvider`, `SofascoreEnrichmentRepository`, `AsyncSessionLocal`
  - Instanciar provider, abrir `AsyncSessionLocal`, instanciar repo y use case, llamar `execute`, hacer `commit`
- [ ] Task `fetch_sofascore_heatmap_task`:
  - `@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)`
  - Firma: `def fetch_sofascore_heatmap_task(self, player_id: int, unique_tournament_id: int, season_id: int)`
  - Body: `asyncio.run(_run_fetch_sofascore_heatmap(player_id, unique_tournament_id, season_id))` dentro de try/except → `raise self.retry(exc=exc)`
- [ ] Helper async `_run_fetch_sofascore_heatmap(player_id, unique_tournament_id, season_id)`:
  - Mismo patrón: imports locales, instanciar, ejecutar, commit

---

### Task 11 — Endpoints admin en `api/v1/admin.py`

**Archivo:** `src/sfa/api/v1/admin.py`

- [ ] Añadir al bloque de imports:
  `from sfa.tasks.sofascore_tasks import enrich_sofascore_photo_task, fetch_sofascore_heatmap_task`
- [ ] Añadir `from pydantic import BaseModel` si no está ya importado
- [ ] Definir body schema (dentro del mismo archivo, antes de los endpoints):
  `class BulkEnrichPhotoRequest(BaseModel): player_ids: list[int]`
- [ ] Endpoint `POST /admin/sofascore/enrich-photo/{player_id}`:
  - Dispara `enrich_sofascore_photo_task.delay(player_id)`
  - Retorna `{"task_id": task.id, "player_id": player_id}`
- [ ] Endpoint `POST /admin/sofascore/fetch-heatmap/{player_id}`:
  - Query params requeridos: `unique_tournament_id: int = Query(...)`, `season_id: int = Query(...)`
  - Dispara `fetch_sofascore_heatmap_task.delay(player_id, unique_tournament_id, season_id)`
  - Retorna `{"task_id": task.id, "player_id": player_id, "unique_tournament_id": unique_tournament_id, "season_id": season_id}`
- [ ] Endpoint `POST /admin/sofascore/enrich-photos-bulk`:
  - Body: `request: BulkEnrichPhotoRequest`
  - Itera `request.player_ids`, dispara `enrich_sofascore_photo_task.delay(pid)` por cada uno
  - Retorna `{"tasks": [{"task_id": t.id, "player_id": pid} for pid, t in ...], "total": len(request.player_ids)}`

---

### Task 12 — Wiring en `core/dependencies.py`

**Archivo:** `src/sfa/core/dependencies.py`

- [ ] Añadir en el bloque de imports de repositorios: `SofascoreEnrichmentRepository`
- [ ] Añadir en el bloque de imports de use cases: `EnrichSofascorePhotoUseCase`, `FetchSofascoreHeatmapUseCase`
- [ ] Añadir import del provider: `from sfa.infrastructure.providers.sofascore_provider import SofascoreProvider`
- [ ] Factory `get_sofascore_provider() -> SofascoreProvider`: retorna `SofascoreProvider()` (stateless, sin sesión)
- [ ] Factory `get_sofascore_enrichment_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> SofascoreEnrichmentRepository`
- [ ] Factory `get_enrich_sofascore_photo_use_case(provider: Annotated[SofascoreProvider, Depends(get_sofascore_provider)], repo: Annotated[SofascoreEnrichmentRepository, Depends(get_sofascore_enrichment_repository)]) -> EnrichSofascorePhotoUseCase`
- [ ] Factory `get_fetch_sofascore_heatmap_use_case(provider: ..., repo: ...) -> FetchSofascoreHeatmapUseCase`
- [ ] Nota: los endpoints admin actuales invocan las tasks Celery directamente (sin DI de FastAPI). Las factories quedan disponibles para uso futuro o si se decide invocar los use cases síncronamente.

---

### Task 13 — Archivo HTTP

**Archivo:** `http/sofascore.http`

- [ ] Crear el archivo con variable `@baseUrl = http://localhost:8000`
- [ ] Incluir los siguientes casos separados por `###`:
  1. `POST {{baseUrl}}/admin/sofascore/enrich-photo/1` — happy path: jugador existente
  2. `POST {{baseUrl}}/admin/sofascore/enrich-photo/99999` — jugador no existente (la task maneja el error)
  3. `POST {{baseUrl}}/admin/sofascore/fetch-heatmap/1?unique_tournament_id=8&season_id=61644` — happy path La Liga 2024/25
  4. `POST {{baseUrl}}/admin/sofascore/fetch-heatmap/1` — sin query params requeridos (espera 422)
  5. `POST {{baseUrl}}/admin/sofascore/enrich-photos-bulk` con `Content-Type: application/json` y body `{"player_ids": [1, 2, 3]}`
  6. `GET {{baseUrl}}/players/1` — verificar que la respuesta incluye el campo `heatmap_url`

---

### Task 14 — Tests

**Archivos:**
- `tests/use_cases/test_enrich_sofascore_photo.py`
- `tests/use_cases/test_fetch_sofascore_heatmap.py`

- [ ] Correr `pytest tests/` antes de escribir ningún test nuevo
  Documentar en comentario al inicio de cada archivo de test si hay fallos preexistentes

#### `test_enrich_sofascore_photo.py`

- [ ] Implementar `FakeSofascoreProvider(SofascoreProviderPort)`:
  - Constructor: `_player_to_return: SofascorePlayerDTO | None`, `search_call_count: int = 0`
  - `search_player`: incrementa `search_call_count`, retorna `_player_to_return`
  - `get_heatmap_url`: retorna URL determinística `f"https://api.sofascore.com/api/v1/player/{sofascore_id}/heatmap/{tid}/{sid}"`
- [ ] Implementar `FakeSofascoreEnrichmentRepository(SofascoreEnrichmentRepositoryPort)`:
  - Constructor: `_player_row: SofascorePlayerRow | None`; registra `updated_sofascore_id`, `updated_photo_url`, `updated_heatmap_url`
  - Todos los métodos implementados correctamente
- [ ] `assert isinstance(FakeSofascoreProvider(...), SofascoreProviderPort)`
- [ ] `assert isinstance(FakeSofascoreEnrichmentRepository(...), SofascoreEnrichmentRepositoryPort)`
- [ ] `test_photo_enrich_success_sets_sofascore_id_and_photo_url`:
  - Jugador sin `sofascore_id` previo; búsqueda retorna match con id=1234
  - Verificar: `result.status == "completed"`, `result.sofascore_id == 1234`, `result.photo_url` contiene `"1234"`
  - Verificar: `repo.updated_sofascore_id == 1234` y `repo.updated_photo_url` no es None
- [ ] `test_photo_enrich_skips_search_when_sofascore_id_already_set`:
  - Jugador con `sofascore_id=5678` ya presente en row
  - Verificar: `fake_provider.search_call_count == 0`
  - Verificar: `result.status == "completed"`, `result.sofascore_id == 5678`
- [ ] `test_photo_enrich_player_not_found_returns_failed`:
  - Repo devuelve `None` para `get_player_for_sofascore`
  - Verificar: `result.status == "failed"`, `"not found"` en `result.error.lower()`
- [ ] `test_photo_enrich_no_match_returns_failed`:
  - Provider devuelve `None` en `search_player`
  - Verificar: `result.status == "failed"`, `"No Sofascore match"` en `result.error`
- [ ] `test_photo_url_constructed_correctly`:
  - Match con `sofascore_id=9999`
  - Verificar: `result.photo_url == "https://img.sofascore.com/api/v1/player/9999/image"`

#### `test_fetch_sofascore_heatmap.py`

- [ ] Reutilizar (importar o redefinir) `FakeSofascoreProvider` y `FakeSofascoreEnrichmentRepository`
- [ ] `test_heatmap_fetch_success_sets_heatmap_url`:
  - Jugador con `sofascore_id=1234`; llamar `execute(player_id=1, unique_tournament_id=8, season_id=61644)`
  - Verificar: `result.status == "completed"`, `result.heatmap_url` contiene `"1234/8/61644"`
  - Verificar: `repo.updated_heatmap_url` no es None
- [ ] `test_heatmap_fetch_fails_without_sofascore_id`:
  - Jugador con `sofascore_id=None`
  - Verificar: `result.status == "failed"`, `"sofascore_id"` en `result.error.lower()`
- [ ] `test_heatmap_fetch_player_not_found`:
  - Repo devuelve `None`
  - Verificar: `result.status == "failed"`, `"not found"` en `result.error.lower()`
- [ ] `test_heatmap_url_constructed_correctly`:
  - `sofascore_id=7777`, `unique_tournament_id=17`, `season_id=52186`
  - Verificar: `result.heatmap_url == "https://api.sofascore.com/api/v1/player/7777/heatmap/17/52186"`

---

### Task 15 — Verificación de estilo

- [ ] `flake8 src/sfa/` — cero errores en archivos nuevos y modificados
  (max-line-length=120, rules: E302, E501, F401, F821, ignore: E203, W503)
- [ ] `isort --check src/sfa/` — imports ordenados (profile=black, line_length=120)
- [ ] `pytest tests/` — todos los tests pasan incluyendo los nuevos de Task 14; cobertura ≥ 80%

---

## Agent Routing Brief

**DDD Designer needed:** no

`SofascorePlayerDTO`, `SofascorePlayerRow` y `SofascoreEnrichmentResult` son DTOs de
transferencia (frozen dataclasses). No introducen invariantes de negocio, no modifican el
modelo de scoring, no añaden nuevos `ActionType` ni multiplicadores. El patrón es idéntico
al enrichment FBref/Understat ya implementado.

| Task | Agente | Skill recomendado |
|------|--------|-------------------|
| Task 1 | Implementación directa (script SQL) | — |
| Task 2 | Implementación directa | — |
| Task 3 | Implementación directa | — |
| Task 4 | Implementación directa | — |
| Task 5 | Implementación directa | — |
| Task 6 | Implementación directa | `/sfa-repository` |
| Task 7 | Implementación directa | `/sfa-use-case` |
| Task 8 | Implementación directa | `/sfa-use-case` |
| Task 9 | Implementación directa | `/sfa-repository` |
| Task 10 | Implementación directa | `/sfa-celery-task` |
| Task 11 | Implementación directa | `/sfa-router` |
| Task 12 | Implementación directa | — |
| Task 13 | Implementación directa | — |
| Task 14 | Implementación directa | `/sfa-test` |
| Task 15 | Implementación directa | — |

**Orden de despacho:** secuencia estricta 1 → 15.
Dependencias críticas:
- Tasks 6, 7, 8 requieren Protocols del Task 3.
- Tasks 7, 8 requieren columna `heatmap_url` del Task 1-2.
- Task 9 requiere `heatmap_url` en `PlayerScoreDTO` (Task 4) y en el modelo (Task 1-2).
- Task 11 requiere tasks del Task 10.
- Task 14 requiere use cases de Tasks 7 y 8.

---

## Verificación end-to-end

1. `pytest tests/` pasa al 100% incluyendo los tests nuevos de Task 14
2. `GET /players/{id}` retorna `heatmap_url: null` para jugadores sin heatmap procesado
3. `POST /admin/sofascore/enrich-photo/{player_id}` con un player_id válido retorna `{"task_id": "...", "player_id": N}`; tras la ejecución de la task, `GET /players/{id}` muestra `photo_url` con URL de Sofascore
4. `POST /admin/sofascore/fetch-heatmap/{player_id}?unique_tournament_id=8&season_id=61644` con un jugador que tiene `sofascore_id` → tras la task, `GET /players/{id}` muestra `heatmap_url` no null
5. `POST /admin/sofascore/fetch-heatmap/{player_id}` sin query params requeridos → respuesta 422
6. `POST /admin/sofascore/enrich-photos-bulk` con body `{"player_ids": [1, 2, 3]}` → retorna 3 task_ids
7. `flake8 src/sfa/` y `isort --check src/sfa/` sin errores
