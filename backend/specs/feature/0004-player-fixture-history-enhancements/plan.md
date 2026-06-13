# 0004 — Historial de partidos: Plan de implementación

## TL;DR

Ampliar `GET /players/{id}/fixtures` con tres capacidades: desglose de acciones por partido,
filtros de texto por nombre de competición y por nombre de rival, y filtro por fecha. Todo el
cambio es de lectura pura — sin migración Alembic, sin nuevas tareas Celery, sin @DDD-Designer.

---

## Archivos a modificar

- [ ] `src/sfa/domain/ports.py` — nuevo DTO `FixtureActionBreakdown`, campo en `PlayerFixtureDTO`, nuevo método en `PlayerEventRepositoryProtocol`
- [ ] `src/sfa/application/use_cases/get_player_fixtures.py` — nuevos parámetros, ensamblado del breakdown
- [ ] `src/sfa/infrastructure/repositories/player_event_repository.py` — nuevo método + predicados SQL
- [ ] `src/sfa/api/v1/schemas/players.py` — campo `breakdown` en `PlayerFixtureSchema`
- [ ] `src/sfa/api/v1/players.py` — nuevos query params en el endpoint de fixtures

## Archivos a crear

- [ ] `tests/use_cases/test_get_player_fixtures.py` — tests del use case con Fake pattern

---

## Checklist de implementación

Procesar en orden. Cada ítem debe completarse y verificarse antes de avanzar al siguiente.

---

### Task 1 — Añadir `FixtureActionBreakdown` y ampliar DTOs en `domain/ports.py`

**Archivo:** `src/sfa/domain/ports.py`

- [ ] Verificar que `from __future__ import annotations` está en la primera línea del archivo

- [ ] Añadir frozen dataclass `FixtureActionBreakdown` inmediatamente antes de `PlayerFixtureDTO`:
  - Campos: `count: int`, `pts: float`
  - Criterio de completitud: `from sfa.domain.ports import FixtureActionBreakdown` no lanza error

- [ ] En `PlayerFixtureDTO`, añadir campo al final del dataclass:
  - `breakdown: dict[str, FixtureActionBreakdown] | None = None`
  - Criterio: el campo tiene default `None` — los call sites existentes que construyen `PlayerFixtureDTO` sin este campo siguen compilando sin modificación

- [ ] En `PlayerEventRepositoryProtocol`, añadir nuevo método después de `get_fixtures_by_player`:
  - Firma exacta:
    `async def get_fixture_breakdown_by_player(self, player_id: int, fixture_ids: list[int]) -> dict[int, dict[str, FixtureActionBreakdown]]: ...`
  - La clave del dict exterior es `fixture_id` (int); la clave del dict interior es el valor string del `EventType`

- [ ] Verificar que los tests existentes siguen pasando (`pytest tests/`) — `PlayerFixtureDTO` ahora
  tiene un campo extra con default; los call sites con keyword args no se rompen

---

### Task 2 — Ampliar `GetPlayerFixturesUseCase` con nuevos parámetros y ensamblado de breakdown

**Archivo:** `src/sfa/application/use_cases/get_player_fixtures.py`

- [ ] Añadir `import dataclasses` y `import datetime` al inicio del archivo (tras `from __future__ import annotations`)

- [ ] Añadir import de `FixtureActionBreakdown` desde `sfa.domain.ports`

- [ ] Ampliar `GetPlayerFixturesUseCaseProtocol.execute` con los nuevos parámetros al final de la firma:
  - `include_breakdown: bool = True`
  - `competition_name: str | None = None`
  - `rival: str | None = None`
  - `date: datetime.date | None = None`
  - Todos con defaults — el Protocol es backward compatible con implementaciones existentes

- [ ] Ampliar `GetPlayerFixturesUseCase.execute` con la misma firma extendida

- [ ] Pasar `competition_name`, `rival` y `date` a `self._event_repo.get_fixtures_by_player(...)` (el repo los acepta en Task 3)

- [ ] Después de obtener `fixtures: list[PlayerFixtureDTO]`, implementar la rama de breakdown:
  - Si `include_breakdown is True` y `len(fixtures) > 0`:
    - Extraer `fixture_ids = [f.fixture_id for f in fixtures]`
    - Llamar `breakdown_map = await self._event_repo.get_fixture_breakdown_by_player(player_id, fixture_ids)`
    - Reconstruir cada fixture: `dataclasses.replace(f, breakdown=breakdown_map.get(f.fixture_id))`
    - Retornar la lista reconstruida
  - Si `include_breakdown is False` o `fixtures` está vacía: retornar la lista tal cual

- [ ] Verificar: el use case no importa nada de `infrastructure/` — solo usa Protocols de `domain/`

---

### Task 3 — Implementar los nuevos predicados y el método de breakdown en `PlayerEventRepository`

**Archivo:** `src/sfa/infrastructure/repositories/player_event_repository.py`

#### Sub-task 3a — Nuevos predicados en `get_fixtures_by_player`

- [ ] Añadir `or_` a los imports de `sqlalchemy` (junto a `func`, `select`)

- [ ] Ampliar la firma de `get_fixtures_by_player` con los nuevos parámetros al final:
  - `competition_name: str | None = None`
  - `rival: str | None = None`
  - `date: datetime.date | None = None`

- [ ] Si `competition_name is not None`: añadir al statement
  `.where(Competition.name.ilike(f"%{competition_name}%"))`

- [ ] Si `rival is not None`: añadir al statement
  `.where(or_(home_alias.c.name.ilike(f"%{rival}%"), away_alias.c.name.ilike(f"%{rival}%")))`

- [ ] Si `date is not None`: añadir al statement
  `.where(func.date(Fixture.played_at) == date)`
  (`func` ya está importado — verificar que está en los imports actuales)

- [ ] Verificar que los predicados existentes (`season`, `competition_id`) no se modifican

- [ ] Criterio de completitud: query con `rival="Real Madrid"` y `date=datetime.date(2024,11,3)` no lanza error de compilación SQLAlchemy

#### Sub-task 3b — Implementar `get_fixture_breakdown_by_player`

- [ ] Añadir import de `FixtureActionBreakdown` desde `sfa.domain.ports`

- [ ] Añadir el nuevo método al final de la clase `PlayerEventRepository` con la firma del Protocol

- [ ] Si `fixture_ids` es lista vacía, retornar `{}` inmediatamente sin ejecutar query

- [ ] Construir la query de agregación usando SQLAlchemy 2.0 async:
  - Seleccionar: `PlayerEvent.fixture_id`, `PlayerEvent.event_type`, `func.count().label("count")`, `func.sum(PlayerEvent.pts).label("pts")`
  - Filtrar: `PlayerEvent.player_id == player_id` AND `PlayerEvent.fixture_id.in_(fixture_ids)`
  - Agrupar: `PlayerEvent.fixture_id`, `PlayerEvent.event_type`

- [ ] Ensamblar el resultado en `dict[int, dict[str, FixtureActionBreakdown]]`:
  - Usar `collections.defaultdict(dict)` para el dict exterior
  - Para cada row: `result[row["fixture_id"]][event_type_str] = FixtureActionBreakdown(count=row["count"], pts=float(row["pts"]))`
  - Donde `event_type_str = row["event_type"].value if hasattr(row["event_type"], "value") else str(row["event_type"])`
  - Retornar `dict(result)` (convertir de defaultdict a dict ordinario)

- [ ] Verificar que `PlayerEventRepository` satisface `PlayerEventRepositoryProtocol` en runtime
  (añadir assertion en un test — ver Task 6)

---

### Task 4 — Ampliar `PlayerFixtureSchema` y el router

**Archivos:** `src/sfa/api/v1/schemas/players.py`, `src/sfa/api/v1/players.py`

#### Sub-task 4a — Schema

- [ ] En `PlayerFixtureSchema`, añadir campo al final:
  - `breakdown: dict[str, BreakdownEntrySchema] | None = None`
  - `BreakdownEntrySchema` ya existe en el mismo archivo — no hay nuevo import

#### Sub-task 4b — Router

- [ ] Añadir `import datetime` en `src/sfa/api/v1/players.py` si no está ya

- [ ] En el endpoint `GET /players/{player_id}/fixtures`, añadir los nuevos query params tras los existentes:
  - `include_breakdown: bool = Query(default=True)`
  - `competition_name: str | None = Query(default=None)`
  - `rival: str | None = Query(default=None)`
  - `date: datetime.date | None = Query(default=None)`

- [ ] Pasar los 4 nuevos parámetros a `use_case.execute(...)`

- [ ] Reemplazar la construcción actual `PlayerFixtureSchema(**f.__dict__)` por construcción explícita:
  - Mapear todos los campos del DTO directamente
  - Para el campo `breakdown`: si `f.breakdown` es `None`, pasar `breakdown=None`; si no, construir
    `{k: BreakdownEntrySchema(count=v.count, pts=v.pts, pct=None) for k, v in f.breakdown.items()}`
  - Verificar que `BreakdownEntrySchema` está importado en el router

- [ ] Verificar que la serialización es correcta: el campo `breakdown` aparece en la respuesta JSON
  con la estructura `{"goal": {"count": 1, "pts": 320.5, "pct": null}}`

---

### Task 5 — Actualizar `http/players.http` con los nuevos casos

**Archivo:** `http/players.http`

- [ ] Añadir caso: `GET /players/{id}/fixtures?include_breakdown=true` (happy path con breakdown)
- [ ] Añadir caso: `GET /players/{id}/fixtures?include_breakdown=false` (sin breakdown, más rápido)
- [ ] Añadir caso: `GET /players/{id}/fixtures?competition_name=Champions` (filtro parcial, case-insensitive)
- [ ] Añadir caso: `GET /players/{id}/fixtures?rival=Barcelona` (filtro por rival parcial)
- [ ] Añadir caso: `GET /players/{id}/fixtures?date=2024-11-03` (filtro por fecha ISO 8601)
- [ ] Añadir caso: `GET /players/{id}/fixtures?rival=Real+Madrid&include_breakdown=true` (combinación)
- [ ] Añadir caso: `GET /players/{id}/fixtures?competition_id=1&competition_name=Liga` (AND semántico)

---

### Task 6 — Tests

**Archivo:** `tests/use_cases/test_get_player_fixtures.py`

- [ ] Correr `pytest tests/` antes de escribir ningún test nuevo — documentar en comentario al inicio
  del archivo qué fallos (si los hay) ya existían antes de este spec

- [ ] Implementar `FakePlayerEventRepository` que implemente `PlayerEventRepositoryProtocol` completo:
  - Todos los métodos del Protocol deben estar presentes (incluido `get_events_by_player`)
  - `get_fixtures_by_player`: retorna `self._fixtures` (configurable en constructor); acepta
    todos los parámetros del Protocol incluyendo los nuevos; registrar los parámetros recibidos
    en `self.last_fixtures_call` para poder inspeccionarlos en los tests
  - `get_fixture_breakdown_by_player`: retorna `self._breakdown_map` (configurable); registrar
    si fue llamado con `self.breakdown_call_count: int = 0` (incrementar en cada llamada)

- [ ] Verificar que `FakePlayerEventRepository` satisface el Protocol:
  `assert isinstance(FakePlayerEventRepository(...), PlayerEventRepositoryProtocol)`

- [ ] Test `test_fixtures_with_breakdown_returns_breakdown_per_fixture`:
  - `_fixtures`: 2 `PlayerFixtureDTO` con `fixture_id=101` y `fixture_id=102`
  - `_breakdown_map`: `{101: {"goal": FixtureActionBreakdown(count=1, pts=320.5)}, 102: {"stats": FixtureActionBreakdown(count=1, pts=85.0)}}`
  - Ejecutar `use_case.execute(player_id=1, include_breakdown=True)`
  - Verificar que ambos DTOs en el resultado tienen `breakdown` no-None
  - Verificar que `result[0].breakdown["goal"].count == 1`
  - Verificar que `result[1].breakdown["stats"].pts == 85.0`

- [ ] Test `test_fixtures_without_breakdown_skips_second_query`:
  - Ejecutar `use_case.execute(player_id=1, include_breakdown=False)`
  - Verificar que `fake_repo.breakdown_call_count == 0`
  - Verificar que los DTOs retornados tienen `breakdown=None`

- [ ] Test `test_fixtures_empty_list_skips_breakdown_query`:
  - `_fixtures`: lista vacía
  - Ejecutar `use_case.execute(player_id=1, include_breakdown=True)`
  - Verificar que `fake_repo.breakdown_call_count == 0`
  - Verificar que el resultado es lista vacía

- [ ] Test `test_fixtures_rival_filter_passed_to_repo`:
  - Ejecutar `use_case.execute(player_id=1, rival="Barcelona")`
  - Verificar que `fake_repo.last_fixtures_call["rival"] == "Barcelona"`

- [ ] Test `test_fixtures_date_filter_passed_to_repo`:
  - Ejecutar `use_case.execute(player_id=1, date=datetime.date(2024, 11, 3))`
  - Verificar que `fake_repo.last_fixtures_call["date"] == datetime.date(2024, 11, 3)`

- [ ] Test `test_fixtures_competition_name_filter_passed_to_repo`:
  - Ejecutar `use_case.execute(player_id=1, competition_name="Champions")`
  - Verificar que `fake_repo.last_fixtures_call["competition_name"] == "Champions"`

- [ ] Test `test_breakdown_assembles_correctly`:
  - `_breakdown_map`: `{101: {"goal": FixtureActionBreakdown(count=2, pts=641.0)}}`
  - Fixture con `fixture_id=101`
  - Verificar que `result[0].breakdown["goal"].count == 2` y `result[0].breakdown["goal"].pts == 641.0`

- [ ] Test `test_fixture_without_breakdown_entry_gets_none`:
  - `_breakdown_map`: `{}` (vacío — ningún fixture tiene breakdown)
  - Ejecutar con `include_breakdown=True`
  - Verificar que el DTO resultante tiene `breakdown=None` (no KeyError)

- [ ] Correr `pytest tests/` al final — todos los tests anteriores (0001, 0002, 0003) deben seguir
  pasando sin modificación

---

## Agent Routing Brief

**DDD Designer needed:** no

`FixtureActionBreakdown` es un DTO de lectura (frozen dataclass con `count` y `pts`). No
introduce invariantes de negocio, no modifica el modelo de scoring, no añade nuevos
multiplicadores ni nuevos `ActionType`. Es equivalente al `BreakdownEntry` que ya existe en
`get_player_detail.py` — misma naturaleza, distinto nivel de agregación.

Todos los cambios son de capa de aplicación, repositorio e interfaz HTTP operando sobre datos
que ya existen en la base de datos.

| Task | Agente | Skill recomendado |
|------|--------|-------------------|
| Task 1 | Implementación directa | — |
| Task 2 | Implementación directa | `/sfa-use-case` |
| Task 3 | Implementación directa | `/sfa-repository` |
| Task 4 | Implementación directa | `/sfa-router` |
| Task 5 | Implementación directa | — |
| Task 6 | Implementación directa | `/sfa-test` |

**Orden de despacho:** Tasks 1 → 2 → 3 → 4 → 5 → 6 en secuencia estricta. Cada task depende
de que el Protocol esté actualizado antes de que la implementación y los tests puedan compilar.

---

## Verificación

1. `pytest tests/` pasa al 100% incluyendo los tests nuevos del Task 6
2. `GET /players/{id}/fixtures` sin parámetros retorna el mismo resultado que antes (backward compatible — campo `breakdown` ausente o `null`)
3. `GET /players/{id}/fixtures?include_breakdown=true` retorna fixtures con `breakdown` no-null que contiene al menos un `event_type` conocido (por ejemplo `"goal"` o `"stats"`)
4. `GET /players/{id}/fixtures?rival=Barcelona` retorna solo partidos donde un equipo cuyo nombre contiene "Barcelona" participó (case-insensitive)
5. `GET /players/{id}/fixtures?date=2024-11-03` retorna solo partidos del 3 de noviembre de 2024
6. `GET /players/{id}/fixtures?competition_name=Champions` retorna solo partidos de competiciones cuyo nombre contiene "Champions"
7. `GET /players/{id}/events` y `GET /players/{id}` no sufren regresión — sus tests y respuestas son idénticos a antes del spec
