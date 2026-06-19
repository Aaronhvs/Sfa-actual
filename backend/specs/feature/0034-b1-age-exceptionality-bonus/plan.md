# Plan: 0034 — B1 Age Exceptionality Bonus

## Archivos a crear

- [ ] `migrations/0034_add_birth_date_to_players.sql` — ALTER TABLE para añadir `birth_date DATE NULL`
- [ ] `src/sfa/domain/enrichment/birth_date_ports.py` — `PlayerBirthDateRawDTO` + `PlayerBirthDateProviderPort` + `BirthDateEnrichmentRepositoryPort`
- [ ] `src/sfa/application/use_cases/enrich_player_birth_dates.py` — `EnrichPlayerBirthDatesUseCase`
- [ ] `src/sfa/infrastructure/repositories/birth_date_enrichment_repository.py` — implementación de `BirthDateEnrichmentRepositoryPort`
- [ ] `src/sfa/tasks/enrich_birth_dates_task.py` — Celery task sync→async wrapper
- [ ] `tests/use_cases/test_enrich_player_birth_dates.py` — tests del use case con Fakes

## Archivos a modificar

- [ ] `src/sfa/infrastructure/models/players/models.py` — añadir columna `birth_date`
- [ ] `src/sfa/domain/scoring/value_objects.py` — `B1AgeExceptionalityBonus`, `_age_at_date`, nuevos campos en `ScoringConfig`
- [ ] `src/sfa/domain/scoring_ports.py` — `player_birth_date: date | None` y `fixture_date: date | None` en `PlayerEventRawContextDTO`
- [ ] `src/sfa/infrastructure/providers/api_football.py` — método `fetch_squad_birth_dates(team_id, season)`
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py` — enriquecer query de `get_events_for_recalc` con `players.birth_date` y `fixtures.played_at`
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py` — lógica de agrupación B1 por fixture + distribución en `_score_individual_event`
- [ ] `src/sfa/core/dependencies.py` — wiring de `EnrichPlayerBirthDatesUseCase`
- [ ] `src/sfa/api/v1/` — endpoint admin para disparar el enrichment manualmente (opcional pero recomendado para el rollout)
- [ ] `src/sfa/tasks/celery_app.py` (o donde viva el beat schedule) — registrar `enrich_birth_dates_task` si se quiere periódico

## Checklist de implementación

### Fase 1 — Migración de base de datos

- [ ] **[MIGRACIÓN SQL]** Crear `migrations/0034_add_birth_date_to_players.sql`:
  ```sql
  ALTER TABLE players ADD COLUMN IF NOT EXISTS birth_date DATE NULL;
  COMMENT ON COLUMN players.birth_date IS 'Date of birth from API-Football player.birth.date';
  ```
- [ ] Añadir columna al modelo ORM `src/sfa/infrastructure/models/players/models.py`:
  ```python
  from sqlalchemy import Date
  birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
  ```
  Añadir también el comentario de migration al final del archivo (patrón ya existente en el modelo).

### Fase 2 — Ports y DTOs de enrichment

- [ ] Crear `src/sfa/domain/enrichment/birth_date_ports.py` con:
  - `PlayerBirthDateRawDTO(external_id: int, birth_date: date | None)` — frozen dataclass
  - `PlayerBirthDateProviderPort(Protocol)`:
    ```python
    async def fetch_squad_birth_dates(
        self, team_id: int, season: int,
    ) -> list[PlayerBirthDateRawDTO]: ...
    ```
  - `BirthDateEnrichmentRepositoryPort(Protocol)`:
    ```python
    async def get_teams_with_players_missing_birth_date(
        self, season: str,
    ) -> list[tuple[int, int]]: ...
    # returns list of (team_external_id, season_int) pairs

    async def upsert_player_birth_date(
        self, external_id: int, birth_date: date | None,
    ) -> None: ...

    async def count_players_missing_birth_date(self) -> int: ...
    ```
  - Ambos Protocols deben ser `@runtime_checkable`.

### Fase 3 — Provider: fetch_squad_birth_dates

- [ ] En `src/sfa/infrastructure/providers/api_football.py` añadir método:
  ```python
  async def fetch_squad_birth_dates(
      self, team_id: int, season: int,
  ) -> list[PlayerBirthDateRawDTO]:
      data = await self._get("players", {"team": team_id, "season": season})
      result = []
      for entry in data.get("response", []):
          player = entry.get("player") or {}
          external_id = player.get("id")
          if not isinstance(external_id, int) or external_id <= 0:
              continue
          raw_date = (player.get("birth") or {}).get("date")
          birth_date = None
          if raw_date:
              try:
                  birth_date = date.fromisoformat(raw_date)
              except (ValueError, TypeError):
                  logger.warning("[APIFootballProvider] Invalid birth.date=%r for player_id=%d", raw_date, external_id)
          result.append(PlayerBirthDateRawDTO(external_id=external_id, birth_date=birth_date))
      return result
  ```
  Importar `PlayerBirthDateRawDTO` desde `sfa.domain.enrichment.birth_date_ports`.
  Importar `date` desde `datetime`.

### Fase 4 — Repository de enrichment

- [ ] Crear `src/sfa/infrastructure/repositories/birth_date_enrichment_repository.py`:
  - `get_teams_with_players_missing_birth_date(season)`:
    Query que busca equipos (via `player_appearances` o `player_stats` JOIN `fixtures`) donde
    algún jugador del equipo tiene `players.birth_date IS NULL` en la temporada dada.
    Devuelve `list[tuple[team_external_id, season_int]]` unique.
    ```sql
    SELECT DISTINCT t.external_id, CAST(ps.season AS INTEGER)
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.id
    JOIN teams t ON ps.team_id = t.id
    WHERE ps.season = :season
      AND p.birth_date IS NULL
      AND t.external_id IS NOT NULL
    ```
  - `upsert_player_birth_date(external_id, birth_date)`:
    ```sql
    UPDATE players SET birth_date = :birth_date
    WHERE external_id = :external_id
    ```
    Solo actualiza si `birth_date IS NULL` o si se fuerza (`force=True` param opcional).
  - `count_players_missing_birth_date()`:
    ```sql
    SELECT COUNT(*) FROM players WHERE birth_date IS NULL AND external_id IS NOT NULL
    ```

### Fase 5 — Use case de enrichment

- [ ] Crear `src/sfa/application/use_cases/enrich_player_birth_dates.py`:
  - Clase `EnrichPlayerBirthDatesResult(frozen dataclass)`:
    `teams_processed: int`, `players_updated: int`, `players_skipped: int`, `status: str`, `error: str | None`
  - Clase `EnrichPlayerBirthDatesUseCase`:
    ```python
    def __init__(
        self,
        provider: PlayerBirthDateProviderPort,
        repo: BirthDateEnrichmentRepositoryPort,
    ) -> None: ...

    async def execute(
        self,
        season: str,
        force_update: bool = False,
    ) -> EnrichPlayerBirthDatesResult: ...
    ```
  - Lógica de `execute`:
    1. Llamar `repo.get_teams_with_players_missing_birth_date(season)` (o todos los teams si `force_update=True`).
    2. Para cada `(team_external_id, season_int)`, llamar `provider.fetch_squad_birth_dates(team_external_id, season_int)`.
    3. Para cada `PlayerBirthDateRawDTO` en la respuesta, llamar `repo.upsert_player_birth_date(external_id, birth_date)`.
    4. Sumar `players_updated` y `teams_processed`.
    5. Log con prefijo `[EnrichPlayerBirthDatesUseCase]`.
    6. Manejo de excepciones: si falla un team, loguear y continuar con el siguiente (no abortar todo).
  - `session.commit()` NO se llama aquí — lo hace la Celery task.

### Fase 6 — Celery task

- [ ] Crear `src/sfa/tasks/enrich_birth_dates_task.py`:
  - Patrón sync→async igual que otras tasks (ver `sfa-celery-task` skill).
  - Función `enrich_player_birth_dates_task(season: str, force_update: bool = False)`.
  - `async with AsyncSessionLocal() as session:` → instanciar repo + provider + use case → `await use_case.execute(season, force_update)` → `await session.commit()`.
  - Log de inicio y fin con `[enrich_player_birth_dates_task]`.
  - No añadir al Beat schedule por defecto — se lanza manualmente o desde el endpoint admin.

### Fase 7 — Domain: B1 value object y ScoringConfig

- [ ] En `src/sfa/domain/scoring/value_objects.py`:
  - Añadir `from datetime import date` al import.
  - Añadir función privada `_age_at_date(birth_date: date, reference_date: date) -> int`:
    ```python
    def _age_at_date(birth_date: date, reference_date: date) -> int:
        age = reference_date.year - birth_date.year
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age
    ```
  - Añadir dataclass `B1AgeExceptionalityBonus`:
    ```python
    @dataclass(frozen=True)
    class B1AgeExceptionalityBonus:
        value: float  # total B1 for the fixture (to be split across N events)

        def __init__(
            self,
            contributions: int,
            player_birth_date: date | None,
            fixture_date: date,
            config: ScoringConfig,
        ) -> None:
            if not config.b1_enabled or player_birth_date is None or contributions == 0:
                object.__setattr__(self, "value", 0.0)
                return
            age = _age_at_date(player_birth_date, fixture_date)
            is_young = config.b1_young_min_age <= age <= config.b1_young_max_age
            is_veteran = age >= config.b1_veteran_min_age
            if not (is_young or is_veteran):
                object.__setattr__(self, "value", 0.0)
                return
            capped = min(contributions, 3)
            bonus = config.b1_bonus_table.get(capped, 0)
            object.__setattr__(self, "value", float(bonus))
    ```
  - En `ScoringConfig`, añadir campos opcionales al final de la clase (después de `stats_m2_attenuation`):
    ```python
    b1_enabled: bool = False
    b1_young_min_age: int = 17
    b1_young_max_age: int = 20
    b1_veteran_min_age: int = 35
    b1_bonus_table: dict[int, int] = field(default_factory=lambda: {1: 200, 2: 400, 3: 600})
    ```
  - En `ScoringConfig.__post_init__`, añadir validaciones:
    ```python
    if self.b1_enabled:
        if not (0 <= self.b1_young_min_age <= self.b1_young_max_age <= 99):
            raise ValueError(f"b1_young age range invalid: [{self.b1_young_min_age}, {self.b1_young_max_age}]")
        if self.b1_veteran_min_age <= 0:
            raise ValueError(f"b1_veteran_min_age must be > 0, got {self.b1_veteran_min_age}")
        if not self.b1_bonus_table:
            raise ValueError("b1_bonus_table cannot be empty when b1_enabled=True")
    ```
  - En `ScoringConfig.from_dict`, añadir deserialización de los 5 campos B1 (con defaults backward-compat):
    ```python
    b1_enabled=bool(d.get("b1_enabled", False)),
    b1_young_min_age=int(d.get("b1_young_min_age", 17)),
    b1_young_max_age=int(d.get("b1_young_max_age", 20)),
    b1_veteran_min_age=int(d.get("b1_veteran_min_age", 35)),
    b1_bonus_table={int(k): int(v) for k, v in d.get("b1_bonus_table", {1: 200, 2: 400, 3: 600}).items()},
    ```
    Nota: las keys del dict vienen como strings de JSON → `int(k)`.
  - En `ScoringConfig.to_dict`, añadir serialización:
    ```python
    "b1_enabled": self.b1_enabled,
    "b1_young_min_age": self.b1_young_min_age,
    "b1_young_max_age": self.b1_young_max_age,
    "b1_veteran_min_age": self.b1_veteran_min_age,
    "b1_bonus_table": {str(k): v for k, v in self.b1_bonus_table.items()},
    ```
    Nota: keys como strings para compatibilidad JSON.
  - En `ScoringConfig.default_v2`, los campos B1 quedan con defaults (b1_enabled=False) — sin cambio explícito.

### Fase 8 — PlayerEventRawContextDTO

- [ ] En `src/sfa/domain/scoring_ports.py`, añadir al final de `PlayerEventRawContextDTO`:
  ```python
  from datetime import date
  # ...
  player_birth_date: date | None = None   # from players.birth_date
  fixture_date: date | None = None        # date portion of fixtures.played_at
  ```
  Ambos con default `None` para no romper código existente que construya el DTO.

### Fase 9 — Repository: enriquecer get_events_for_recalc

- [ ] En `src/sfa/infrastructure/repositories/player_event_score_repository.py`, modificar
  la query de `get_events_for_recalc` para hacer JOIN con `players` y `fixtures`:
  ```sql
  -- Añadir a los campos del SELECT:
  p.birth_date AS player_birth_date,
  CAST(f.played_at AS DATE) AS fixture_date
  -- JOIN ya debería existir o añadir:
  JOIN players p ON pe.player_id = p.id
  JOIN fixtures f ON pe.fixture_id = f.id
  ```
  Al construir el `PlayerEventRawContextDTO` en el mapper, rellenar:
  ```python
  player_birth_date=row.player_birth_date,   # puede ser None
  fixture_date=row.fixture_date,             # puede ser None
  ```

### Fase 10 — Use case de scoring: aplicar B1

- [ ] En `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`:

  **Paso A — Precarga del mapa de contribuciones por fixture**

  En `execute()`, antes del loop de eventos, construir el mapa:
  ```python
  # Only if B1 is enabled in config
  b1_contributions_map: dict[tuple[int, int], int] = {}  # (player_id, fixture_id) -> count
  if rules_version.config.b1_enabled:
      b1_contributions_map = _build_b1_contributions_map(events)
  ```
  Función helper privada `_build_b1_contributions_map`:
  ```python
  _B1_ELIGIBLE_ACTIONS = frozenset({
      "goal", "goal_penalty", "assist", "corner_assist"
  })

  def _build_b1_contributions_map(
      events: list[PlayerEventRawContextDTO],
  ) -> dict[tuple[int, int], int]:
      result: dict[tuple[int, int], int] = {}
      for ev in events:
          if ev.event_type in _B1_ELIGIBLE_ACTIONS:
              key = (ev.player_id, ev.fixture_id)
              result[key] = result.get(key, 0) + 1
      return result
  ```

  **Paso B — Pasar el mapa a `_score_event`**

  Modificar la firma de `_score_event` y `_score_individual_event` para recibir
  `b1_contributions_map: dict[tuple[int, int], int]`.

  En `execute()`:
  ```python
  score = self._score_event(
      event, service, rules_version_id, competition_name_map,
      b1_contributions_map=b1_contributions_map,
  )
  ```

  **Paso C — Calcular y distribuir B1 en `_score_individual_event`**

  Al final de `_score_individual_event`, después de calcular `final`:
  ```python
  b1_bonus_total = 0.0
  b1_per_event = 0.0
  b1_audit: dict = {"enabled": False}

  if config.b1_enabled and event.player_birth_date is not None and event.fixture_date is not None:
      key = (event.player_id, event.fixture_id)
      total_contributions = b1_contributions_map.get(key, 0)
      if total_contributions > 0:
          b1_vo = B1AgeExceptionalityBonus(
              contributions=total_contributions,
              player_birth_date=event.player_birth_date,
              fixture_date=event.fixture_date,
              config=config,
          )
          b1_bonus_total = b1_vo.value
          # Distribute evenly among N events in this fixture
          b1_per_event = round(b1_bonus_total / total_contributions, 2)
          final = round(final + b1_per_event, 2)
          age = _age_at_date(event.player_birth_date, event.fixture_date)
          b1_audit = {
              "enabled": True,
              "age_at_match": age,
              "total_contributions": total_contributions,
              "b1_total": b1_bonus_total,
              "b1_per_event": b1_per_event,
          }
  ```
  Importar `B1AgeExceptionalityBonus` y `_age_at_date` desde `sfa.domain.scoring.value_objects`.
  Añadir `"b1_bonus": b1_audit` al dict `details`.

### Fase 11 — Wiring en dependencies.py

- [ ] En `src/sfa/core/dependencies.py`, añadir factory:
  ```python
  async def get_birth_date_enrichment_repository(
      session: Annotated[AsyncSession, Depends(get_session)],
  ) -> BirthDateEnrichmentRepository:
      return BirthDateEnrichmentRepository(session)

  async def get_enrich_player_birth_dates_use_case(
      provider: Annotated[APIFootballProvider, Depends(get_api_football_provider)],
      repo: Annotated[BirthDateEnrichmentRepository, Depends(get_birth_date_enrichment_repository)],
  ) -> EnrichPlayerBirthDatesUseCase:
      return EnrichPlayerBirthDatesUseCase(provider, repo)
  ```

### Fase 12 — Endpoint admin (opcional pero recomendado para rollout)

- [ ] En `src/sfa/api/v1/` crear o añadir a un router existente de admin:
  ```
  POST /api/v1/admin/enrich-birth-dates?season=2026&force_update=false
  ```
  Response: `{ "teams_processed": N, "players_updated": N, "status": "completed" }`
  Usar `EnrichPlayerBirthDatesUseCase` inyectado vía DI.
  Crear `.http` en `http/admin.http` con happy path + force_update=true.

### Fase 13 — Tests

- [ ] Correr `pytest tests/` antes de escribir tests nuevos y documentar fallos existentes.
- [ ] Crear `tests/use_cases/test_enrich_player_birth_dates.py`:
  - `FakePlayerBirthDateProvider(PlayerBirthDateProviderPort)` — implementa el Protocol completo.
  - `FakeBirthDateEnrichmentRepository(BirthDateEnrichmentRepositoryPort)` — implementa el Protocol completo.
  - Test `test_enrich_updates_players_with_missing_birth_date` — happy path.
  - Test `test_enrich_skips_players_already_have_birth_date` — `force_update=False` no sobreescribe.
  - Test `test_enrich_force_update_overwrites_existing` — `force_update=True` sí sobreescribe.
  - Test `test_enrich_handles_provider_error_gracefully` — fallo en un team no aborta el proceso.
  - Test `test_enrich_null_birth_date_stored_when_api_returns_none` — API devuelve birth=null → `None` en DB.
- [ ] Crear `tests/domain/test_b1_age_exceptionality_bonus.py`:
  - Test `test_b1_disabled_in_config_returns_zero`.
  - Test `test_b1_young_player_1_contribution_returns_200`.
  - Test `test_b1_young_player_2_contributions_returns_400`.
  - Test `test_b1_young_player_3plus_contributions_capped_at_600`.
  - Test `test_b1_veteran_player_qualifies`.
  - Test `test_b1_adult_player_21_34_returns_zero`.
  - Test `test_b1_boundary_17_qualifies`.
  - Test `test_b1_boundary_20_qualifies`.
  - Test `test_b1_boundary_21_does_not_qualify`.
  - Test `test_b1_boundary_34_does_not_qualify`.
  - Test `test_b1_boundary_35_qualifies`.
  - Test `test_b1_none_birth_date_returns_zero`.
  - Test `test_age_at_date_birthday_already_passed`.
  - Test `test_age_at_date_birthday_not_yet_passed`.
  - Test `test_age_at_date_exact_birthday`.
- [ ] Crear `tests/domain/test_scoring_config_b1_serialization.py`:
  - Test `test_scoring_config_b1_roundtrip_to_dict_from_dict`.
  - Test `test_scoring_config_b1_defaults_backward_compat` — config v2 sin campos B1 → b1_enabled=False.
  - Test `test_scoring_config_b1_validation_empty_table_when_enabled`.
- [ ] Verificar `pytest tests/` pasa con coverage ≥80%.
- [ ] Verificar `flake8 src/ tests/` sin errores.
- [ ] Verificar `isort --check-only src/ tests/` sin errores.

### Fase 14 — Nueva ScoringRulesVersion con B1 activo (rollout)

- [ ] Una vez que `birth_date` esté enriquecido en DB, crear la nueva versión de reglas
  vía el endpoint existente de admin de scoring rules:
  ```http
  POST /api/v1/scoring-rules/versions
  {
    "name": "v2.2-b1-age-bonus",
    "version": "2.2",
    "description": "v2.1 + B1 age exceptionality bonus",
    "config": {
      // ... mismo config que v4 activo ...
      "b1_enabled": true,
      "b1_young_min_age": 17,
      "b1_young_max_age": 20,
      "b1_veteran_min_age": 35,
      "b1_bonus_table": {"1": 200, "2": 400, "3": 600}
    }
  }
  ```
  Este paso NO es automático — lo ejecuta el operador manualmente.
- [ ] Ejecutar `enrich_player_birth_dates_task` para la temporada 2026.
- [ ] Verificar `count_players_missing_birth_date` devuelve un número aceptable (objetivo: <5% de jugadores activos sin `birth_date`).
- [ ] Ejecutar `calculate_scores_for_rules_version_task` con el nuevo `rules_version_id` y `season=2026`.
- [ ] Activar la nueva versión como activa: `POST /api/v1/scoring-rules/versions/{id}/activate`.

## Agent Routing Brief

**DDD Designer needed:** no

B1 es una extensión de valor (value object `B1AgeExceptionalityBonus`) que añade un bonus
aditivo al pipeline de scoring de eventos individuales ya existente. No introduce entidades
de dominio con identidad ni invariantes complejas que requieran modelado DDD. El cálculo
de edad es una función pura (input: dos fechas → output: entero). El `ScoringConfig` ya es
el mecanismo establecido para parámetros versionados. El enrichment de `birth_date` sigue
el patrón hexagonal estándar (Provider + Repository + UseCase) igual que los enrichments
existentes en el proyecto.

## Verificación

1. **Migración aplicada:**
   ```sql
   SELECT column_name, data_type, is_nullable
   FROM information_schema.columns
   WHERE table_name = 'players' AND column_name = 'birth_date';
   -- Esperado: date, YES
   ```

2. **Enrichment funciona:**
   ```bash
   # Lanzar task manualmente desde Celery
   celery -A sfa.tasks.celery_app call sfa.tasks.enrich_birth_dates_task.enrich_player_birth_dates_task --args='["2026"]'
   ```
   ```sql
   SELECT COUNT(*) FROM players WHERE birth_date IS NOT NULL;
   -- Debe crecer
   ```

3. **B1 aparece en calculation_details:**
   ```sql
   SELECT calculation_details->'b1_bonus'
   FROM player_event_scores pes
   JOIN players p ON pes.player_id = p.id
   WHERE p.birth_date IS NOT NULL
     AND pes.action_type IN ('goal','assist','goal_penalty','corner_assist')
     AND pes.rules_version_id = <nuevo_version_id>
   LIMIT 5;
   -- Debe tener "enabled": true para jugadores 17-20 o 35+
   ```

4. **Score de un jugador joven con gol se incrementa exactamente en 200/contributions:**
   Verificar manualmente con un jugador conocido (ej. Lamine Yamal — nacido 13/07/2007):
   ```sql
   SELECT p.name, p.birth_date, pes.action_type, pes.final_points,
          pes.calculation_details->'b1_bonus' AS b1
   FROM player_event_scores pes
   JOIN players p ON pes.player_id = p.id
   WHERE p.name ILIKE '%Yamal%'
     AND pes.rules_version_id = <nuevo_version_id>;
   ```
   Confirmar que `b1_bonus.age_at_match` es correcto y `b1_per_event = 200.0` para 1 contribución.

5. **Jugador adulto (22 años) no recibe B1:**
   Verificar que `b1_bonus.enabled = false` en sus eventos.

6. **Backward compat: scores con rules_version_id anterior no cambian:**
   ```sql
   SELECT final_points FROM player_event_scores
   WHERE rules_version_id = <version_anterior>
   LIMIT 100;
   -- Valores idénticos a antes del deploy
   ```

7. **Tests pasan:**
   ```bash
   pytest tests/ -v --tb=short
   ```
