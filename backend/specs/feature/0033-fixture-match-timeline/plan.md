# Plan: 0033 — Fixture Match Timeline

## Archivos a crear

- [x] `src/sfa/infrastructure/models/fixture_events/models.py` — modelo `FixtureEvent` (tabla `fixture_events`)
- [x] `src/sfa/tasks/ingest_fixture_events_task.py` — Celery task de backfill por fixture_external_id
- [x] `http/fixture_events.http` — casos HTTP del endpoint (backfill admin + WC detail con events)
- [x] `tests/use_cases/test_ingest_fixture_events.py` — tests de normalización de eventos
- [x] `frontend/src/components/mundial/MatchTimeline.tsx` — componente timeline
- [x] `migrations/0033_create_fixture_events.sql` — migración SQL para producción

## Archivos a modificar

- [x] `src/sfa/infrastructure/models/__init__.py` — importar `FixtureEvent` y registrarlo en `__all__`
- [x] `src/sfa/domain/ingestion_ports.py` — añadir `save_fixture_events()` a `IngestionRepositoryProtocol`
- [x] `src/sfa/domain/world_cup_ports.py` — añadir `WorldCupFixtureEventDTO` + `get_fixture_events()` a `WorldCupRepositoryProtocol` + campo `events` en `WorldCupFixtureDetailDTO`
- [x] `src/sfa/infrastructure/repositories/ingestion_repository.py` — implementar `save_fixture_events()`
- [x] `src/sfa/infrastructure/repositories/world_cup_repository.py` — implementar `get_fixture_events()`
- [x] `src/sfa/application/use_cases/ingest_competition.py` — llamar `save_fixture_events()` tras procesar cada fixture
- [x] `src/sfa/application/use_cases/get_world_cup.py` — `GetWorldCupFixtureDetailUseCase` incluye `events`
- [x] `src/sfa/api/v1/schemas/wc_schemas.py` — añadir `WcFixtureEventSchema` + campo `events` en `WcFixtureDetailResponseSchema`
- [x] `src/sfa/api/v1/wc_router.py` — mapear `events` al response
- [x] `src/sfa/api/v1/admin.py` — añadir `POST /admin/fixtures/{fixture_external_id}/ingest-events`
- [x] `src/sfa/tasks/__init__.py` — registrar `ingest_fixture_events_task`
- [x] `frontend/src/types/index.ts` — añadir `WcFixtureEvent` y extender `WcFixtureDetailResponse`
- [x] `frontend/src/pages/MundialMatchPage.tsx` — importar y montar `MatchTimeline` sobre el pitch

## Checklist de implementación

### Backend — Modelo

- [x] Crear `src/sfa/infrastructure/models/fixture_events/models.py` con el modelo `FixtureEvent`:
  ```
  id (PK), fixture_external_id (int, sin FK a fixtures), minute (SmallInt), extra_minute (SmallInt default 0),
  team_external_id (Int, sin FK), event_type (String 30), player_name (String 150 default ''),
  assist_name (String 150 nullable), source_sequence (SmallInt nullable)
  ```
  Índice `ix_fixture_events_fixture_external_id` sobre `fixture_external_id`.

  **Decisión clave:** se usa `fixture_external_id` (int, sin FK) en lugar de `fixture_id FK→fixtures.id`
  porque los fixtures WC se obtienen en tiempo real de API-Football y no están almacenados en
  la tabla `fixtures` local. Un FK silenciaría todos los eventos al no encontrar la fila.

- [x] Importar `FixtureEvent` en `src/sfa/infrastructure/models/__init__.py` y agregarlo a `__all__`.
  La tabla se crea automáticamente vía `Base.metadata.create_all` en el startup.

### Backend — Domain Ports

- [x] En `src/sfa/domain/ingestion_ports.py`, añadir método al `IngestionRepositoryProtocol`:
  ```python
  async def save_fixture_events(
      self, fixture_external_id: int, events: list[FixtureEventRawDTO]
  ) -> None: ...
  ```

- [x] En `src/sfa/domain/world_cup_ports.py`:
  - Añadir nuevo DTO frozen:
    ```python
    @dataclass(frozen=True)
    class WorldCupFixtureEventDTO:
        minute: int
        extra_minute: int
        team_external_id: int
        event_type: str        # 'goal' | 'own_goal' | 'penalty' | 'missed_penalty' | 'yellow_card' | 'red_card' | 'yellow_red_card' | 'substitution'
        player_name: str
        assist_name: str | None
    ```
  - Añadir campo `events: list[WorldCupFixtureEventDTO] = field(default_factory=list)`
    a `WorldCupFixtureDetailDTO`. Campo **opcional** para no romper constructores existentes
    (provider, tests, deserialización de caché Redis).
  - Añadir método al `WorldCupRepositoryProtocol`:
    ```python
    async def get_fixture_events(self, fixture_external_id: int) -> list[WorldCupFixtureEventDTO]: ...
    ```

### Backend — Repositories

- [x] En `src/sfa/infrastructure/repositories/ingestion_repository.py`, implementar `save_fixture_events`:
  - Recibe `fixture_external_id` (int) y lista de `FixtureEventRawDTO`.
  - **No resuelve fixture_id interno** — escribe directo con `fixture_external_id`.
  - Para cada DTO, normalizar el `event_type` con la función privada `_normalize_fixture_event_type(type, detail) -> str | None`.
    Si retorna `None`, skip (VAR y desconocidos).
  - Idempotencia: `DELETE FROM fixture_events WHERE fixture_external_id = :ext_id`, luego bulk insert.

  **Lógica de normalización** (función privada `_normalize_fixture_event_type` en el mismo módulo):
  ```
  type="Goal", detail contiene "Own Goal"       → "own_goal"
  type="Goal", detail contiene "Missed Penalty"  → "missed_penalty"
  type="Goal", detail contiene "Penalty"         → "penalty"
  type="Goal"  (resto)                           → "goal"
  type="Card", detail contiene "Yellow Red"      → "yellow_red_card"
  type="Card", detail contiene "Red Card"        → "red_card"
  type="Card"  (resto)                           → "yellow_card"
  type="subst" (cualquier detail)                → "substitution"
  type="Var"   (cualquier detail)                → None  ← skip
  ```
  Comparaciones case-insensitive.

- [x] En `src/sfa/infrastructure/repositories/world_cup_repository.py`, implementar `get_fixture_events`:
  - `SELECT * FROM fixture_events WHERE fixture_external_id = :ext_id ORDER BY minute ASC, extra_minute ASC, source_sequence ASC NULLS LAST`.
  - Retornar lista de `WorldCupFixtureEventDTO`. Si no hay filas, retornar `[]`.
  - En `_detail_from_dict()` (deserialización desde caché Redis), pasar `events=[]` al constructor.

### Backend — Use Cases

- [x] En `src/sfa/application/use_cases/ingest_competition.py`, tras el bloque donde se procesan
  los eventos de un fixture para scoring, añadir:
  ```python
  await self._repo.save_fixture_events(fixture.external_id, events)
  ```
  El `events` ya existe en ese scope (es la lista raw de `fetch_fixture_events`).

- [x] En `src/sfa/application/use_cases/get_world_cup.py`, en `GetWorldCupFixtureDetailUseCase.execute()`:
  - Añadir `events = await self._repository.get_fixture_events(fixture_id)`.
  - Usar `dataclasses.replace(detail, events=events)` para retornar el DTO con eventos inyectados.

### Backend — Celery Task (backfill)

- [x] Crear `src/sfa/tasks/ingest_fixture_events_task.py` con la task `ingest_fixture_events_task(fixture_external_id: int)`:
  - Llama `provider.fetch_fixture_events(fixture_external_id)`.
  - Llama `ingestion_repo.save_fixture_events(fixture_external_id, events)`.
  - Late imports obligatorios (patrón existente en `tasks/`).
  - No registrar en beat schedule (se invoca manualmente desde admin/HTTP).
  - Registrar en `tasks/__init__.py` (`from .ingest_fixture_events_task import ingest_fixture_events_task`).

- [x] Crear `http/fixture_events.http` con:
  - `POST /admin/fixtures/{fixture_external_id}/ingest-events` (backfill un partido)
  - `GET /wc/fixtures/{fixture_external_id}` con ejemplo de response incluyendo `events`

### Backend — API

- [x] En `src/sfa/api/v1/schemas/wc_schemas.py`:
  - Añadir `WcFixtureEventSchema(BaseModel)` con campos:
    `minute`, `extra_minute`, `team_external_id`, `event_type`, `player_name`, `assist_name`.
  - Añadir campo `events: list[WcFixtureEventSchema] = []` a `WcFixtureDetailResponseSchema`.

- [x] En `src/sfa/api/v1/wc_router.py`, en `get_wc_fixture_detail`, mapear
  `events=[WcFixtureEventSchema(**e.__dict__) for e in detail.events]`.

- [x] En `src/sfa/api/v1/admin.py`, añadir endpoint `POST /admin/fixtures/{fixture_external_id}/ingest-events`
  que encola o ejecuta directamente `ingest_fixture_events_task`.

### Frontend — Tipos

- [x] En `frontend/src/types/index.ts`:
  - Añadir interfaz:
    ```typescript
    export interface WcFixtureEvent {
      minute: number
      extra_minute: number
      team_external_id: number
      event_type: string
      player_name: string
      assist_name: string | null
    }
    ```
  - Añadir campo `events: WcFixtureEvent[]` a la interfaz `WcFixtureDetailResponse`.

### Frontend — Componente MatchTimeline

- [x] Crear `frontend/src/components/mundial/MatchTimeline.tsx`. Props:
  ```typescript
  { events: WcFixtureEvent[], homeTeamExternalId: number }
  ```
  
  **Lógica de render por `event_type`:**
  | event_type | Label | Descripción |
  |---|---|---|
  | `goal` | `GOL` | `player_name` + si hay `assist_name`: nota de asistencia |
  | `own_goal` | `GOL EN CONTRA` | `player_name` |
  | `penalty` | `GOL (PENAL)` | `player_name` |
  | `missed_penalty` | `PENAL FALLADO` | `player_name` |
  | `yellow_card` | `AMARILLA` | `player_name` |
  | `red_card` | `ROJA` | `player_name` |
  | `yellow_red_card` | `DOBLE AMARILLA` | `player_name` |
  | `substitution` | `CAMBIO` | `assist_name` entra / `player_name` sale |

  **Layout:** dos columnas (home | away). Evento del equipo home va a la izquierda, away a la
  derecha. Si `events` está vacío, no renderizar el componente (return null).

  No usar emojis. Sin imágenes de jugadores (no hay `player_photo_url` en el backend).
  Usar clases CSS propias (`wmd-timeline__*`).

- [x] Añadir CSS de `MatchTimeline` en `frontend/src/index.css` bajo las clases `.wmd-*` existentes.

- [x] En `frontend/src/pages/MundialMatchPage.tsx`:
  - Importar `MatchTimeline`.
  - Renderizar `<MatchTimeline>` **ANTES** de `<CombinedTacticalPitch>` (encima de las formaciones).

### Migración SQL

- [x] Crear `migrations/0033_create_fixture_events.sql`:
  ```sql
  CREATE TABLE IF NOT EXISTS fixture_events (
      id                  serial          PRIMARY KEY,
      fixture_external_id integer         NOT NULL,
      minute              smallint        NOT NULL,
      extra_minute        smallint        NOT NULL DEFAULT 0,
      team_external_id    integer         NOT NULL,
      event_type          varchar(30)     NOT NULL,
      player_name         varchar(150)    NOT NULL DEFAULT '',
      assist_name         varchar(150),
      source_sequence     smallint,
      CONSTRAINT ck_fixture_event_type CHECK (
          event_type IN ('goal','own_goal','penalty','missed_penalty',
                         'yellow_card','red_card','yellow_red_card','substitution')
      )
  );
  CREATE INDEX IF NOT EXISTS ix_fixture_events_fixture_external_id
      ON fixture_events (fixture_external_id);
  ```
  Ejecutar en VPS **antes** de reiniciar la API (tabla se crea sola en dev vía `create_all`,
  pero en producción la migración es obligatoria).

### Tests

- [x] Crear `tests/use_cases/test_ingest_fixture_events.py`:
  - Tests de `_normalize_fixture_event_type` (función privada en `ingestion_repository.py`):
    - goal, own_goal, penalty, missed_penalty, yellow_card, red_card, yellow_red_card, substitution
    - VAR → None, tipo desconocido → None
  - `TestNormalizationCoverage` parametrizado: 11 variantes de API-Football.

- [x] Actualizar `tests/use_cases/test_get_world_cup.py`:
  - Añadir `get_fixture_events()` a `FakeWorldCupRepository` (retorna `[]`).
  - Añadir import de `WorldCupFixtureEventDTO`.

- [ ] Verificar `pytest tests/` pasa sin errores nuevos
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed:** no

La feature no introduce nuevas entidades de dominio con invariantes de negocio. `FixtureEvent`
es un registro de datos de display (raw storage + projection). No hay value objects nuevos,
no hay reglas de scoring, no hay aggregates. El único "modelo de dominio" nuevo es un DTO
frozen (`WorldCupFixtureEventDTO`) que es de lectura pura — no requiere DDD Designer.

## Verificación

1. Aplicar migración: `psql -U sfa -d sfa -f migrations/0033_create_fixture_events.sql`
2. Reiniciar API y worker.
3. Backfill un partido: `POST /api/v1/admin/fixtures/1539016/ingest-events`
4. Verificar en DB:
   ```sql
   SELECT fixture_external_id, event_type, minute, player_name
   FROM fixture_events
   WHERE fixture_external_id = 1539016
   ORDER BY minute, extra_minute;
   ```
5. `GET /api/v1/wc/fixtures/1539016` — debe incluir campo `events` con la lista ordenada.
6. Abrir `http://localhost:5173/mundial/partido/1539016` — debe mostrarse `MatchTimeline`
   encima de las formaciones, con eventos correctamente asignados a home/away.
7. Partido sin eventos ingested: `events: []` en el response, componente no se renderiza.
8. Confirmar que `ingest_competition_task` sigue funcionando para partidos nuevos (Celery Beat).
