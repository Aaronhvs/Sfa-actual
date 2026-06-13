# Plan: Rating-Based Stats Multiplier (Mrating)

## Archivos a crear

- [ ] `backend/migrations/versions/XXXX_add_rating_to_player_stats.py` — migración Alembic
      que añade columna `rating FLOAT NULL` a la tabla `player_stats`

## Archivos a modificar

- [ ] `backend/src/sfa/domain/scoring/value_objects.py` — añadir clase `MratingFactor`
- [ ] `backend/src/sfa/domain/scoring/services.py` — añadir parámetro `rating` a
      `score_match_stats()` y aplicar `MratingFactor` al multiplicador combinado
- [ ] `backend/src/sfa/domain/ingestion_ports.py` — añadir campo `rating: float | None = None`
      en `PlayerStatsRawDTO`
- [ ] `backend/src/sfa/domain/enrichment_ports.py` — añadir campo `rating: float | None` en
      `PlayerStatsEventRecalcRow`
- [ ] `backend/src/sfa/domain/ports.py` — añadir campo `rating: float | None = None` en
      `PlayerFixtureDTO`
- [ ] `backend/src/sfa/infrastructure/providers/api_football.py` — extraer y convertir
      `games.rating` (str → float | None) en `fetch_fixture_players()`
- [ ] `backend/src/sfa/infrastructure/models/player_stats/models.py` — añadir columna
      `rating: Mapped[float | None]` al modelo `PlayerStats`
- [ ] `backend/src/sfa/application/use_cases/ingest_competition.py` — pasar `ps.rating` al
      `upsert_player_stats()` y al `score_match_stats()`
- [ ] `backend/src/sfa/application/use_cases/recalculate_scores.py` — leer `event.rating` de
      `PlayerStatsEventRecalcRow` y aplicar `MratingFactor` en el cálculo de stats
- [ ] `backend/src/sfa/infrastructure/repositories/` (repositorio de ingestion) — incluir
      `rating` en el `INSERT/UPDATE` de `upsert_player_stats()`
- [ ] `backend/src/sfa/infrastructure/repositories/` (repositorio de enrichment) — incluir
      `rating` en la query de `get_stats_events_for_recalc()`
- [ ] `frontend/src/types/index.ts` — añadir campo `rating: number | null` en `PlayerFixture`
- [ ] `frontend/src/components/player/FixtureRow.tsx` — mostrar el rating como número dorado
      junto a los pts del partido

---

## Checklist de implementación

### Paso 1 — Domain: value object MratingFactor [DDD]

- [ ] En `domain/scoring/value_objects.py`, añadir `@dataclass(frozen=True) class MratingFactor`
      con constructor `(rating: float | None)` y atributo `value: float`.
- [ ] La lógica de escala sigue exactamente la tabla aprobada:
      `None → 0.5`, `< 7.0 → 0.3`, `[7.0, 8.0) → 0.5`, `[8.0, 8.5) → 0.75`, `>= 8.5 → 1.0`.
- [ ] Usar `object.__setattr__(self, "value", v)` igual que los demás value objects frozen.
- [ ] Exportar `MratingFactor` en los imports de `domain/scoring/services.py`.

### Paso 2 — Domain: modificar `score_match_stats()`

- [ ] Añadir parámetro `rating: float | None` al método `score_match_stats()` en
      `SFAScoringService`.
- [ ] Instanciar `MratingFactor(rating)` dentro del método.
- [ ] Cambiar el cálculo de `combined`: de `max(0.3, min(4.0, m1.value))`
      a `max(0.3, min(4.0, m1.value * mrating.value))`.
- [ ] El resto del método (iteración por action, base_pts) permanece idéntico.
- [ ] Actualizar el docstring del método para reflejar el nuevo multiplicador.

### Paso 3 — Infra: modelo SQLAlchemy

- [ ] En `infrastructure/models/player_stats/models.py`, añadir columna:
      `rating: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True, default=None)`.
- [ ] No añadir `CheckConstraint` para rating (valores de API pueden variar; se confía en el
      clamping del value object, no en la DB).

### Paso 4 — Infra: migración Alembic

- [ ] Generar migración con `alembic revision --autogenerate -m "add_rating_to_player_stats"`.
- [ ] Verificar que el archivo generado contiene `op.add_column('player_stats', sa.Column('rating', sa.Numeric(4,2), nullable=True))`.
- [ ] Verificar `op.drop_column('player_stats', 'rating')` en el `downgrade`.

### Paso 5 — Infra: provider API-Football

- [ ] En `APIFootballProvider.fetch_fixture_players()`, dentro del bloque de construcción de
      `PlayerStatsRawDTO`, extraer `games.get("rating")`.
- [ ] Convertir a float con `try/except (TypeError, ValueError)` produciendo `None` en caso
      de fallo o valor nulo.
- [ ] Pasar el resultado como `rating=<valor>` al constructor de `PlayerStatsRawDTO`.

### Paso 6 — Domain DTO: `PlayerStatsRawDTO`

- [ ] En `domain/ingestion_ports.py`, añadir `rating: float | None = None` como campo con
      default al final de `PlayerStatsRawDTO` (campo opcional para no romper tests existentes).

### Paso 7 — Infra: repositorio de ingestion (`upsert_player_stats`)

- [ ] Localizar la implementación concreta de `IngestionRepositoryPort.upsert_player_stats()`
      en `infrastructure/repositories/`.
- [ ] Añadir `rating` al dict de stats que se persiste: el `stats` dict pasado desde el use
      case ya incluirá `"rating": ps.rating`; asegurar que el `INSERT/UPDATE` lo mapea a la
      columna `player_stats.rating`.

### Paso 8 — Application: `IngestCompetitionUseCase`

- [ ] En el bloque de `upsert_player_stats()`, añadir `"rating": ps.rating` al dict de stats.
- [ ] En el bloque de `score_match_stats()`, pasar `rating=ps.rating` como argumento adicional.

### Paso 9 — Domain DTO: `PlayerStatsEventRecalcRow`

- [ ] En `domain/enrichment_ports.py`, añadir `rating: float | None` a
      `PlayerStatsEventRecalcRow`.

### Paso 10 — Infra: repositorio de enrichment (`get_stats_events_for_recalc`)

- [ ] Localizar la implementación concreta de `EnrichmentRepositoryPort.get_stats_events_for_recalc()`
      en `infrastructure/repositories/`.
- [ ] Añadir `player_stats.rating` a la query SELECT.
- [ ] Incluir `rating=row.rating` en la construcción del `PlayerStatsEventRecalcRow`.

### Paso 11 — Application: `RecalculateScoresUseCase`

- [ ] En la Phase 2 (stats events), instanciar `MratingFactor(event.rating)`.
- [ ] Cambiar el cálculo de `combined` de `max(0.3, min(4.0, event.m1))`
      a `max(0.3, min(4.0, event.m1 * mrating.value))`.
- [ ] Importar `MratingFactor` desde `domain/scoring/value_objects`.

### Paso 12 — Domain DTO: `PlayerFixtureDTO` (read-side)

- [ ] En `domain/ports.py`, añadir `rating: float | None = None` a `PlayerFixtureDTO`.

### Paso 13 — Infra: repositorio read-side (fixtures por jugador)

- [ ] Localizar la implementación concreta de `PlayerEventRepositoryProtocol.get_fixtures_by_player()`
      en `infrastructure/repositories/`.
- [ ] Añadir `player_stats.rating` al SELECT y mapearlo a `PlayerFixtureDTO.rating`.

### Paso 14 — API: schema Pydantic de respuesta de fixtures

- [ ] Localizar el schema Pydantic que serializa `PlayerFixtureDTO` hacia el frontend
      (en `api/v1/schemas/`).
- [ ] Añadir campo `rating: float | None = None` al schema de respuesta.

### Paso 15 — Frontend: tipo TypeScript

- [ ] En `frontend/src/types/index.ts`, añadir `rating: number | null` en la interfaz
      `PlayerFixture`.

### Paso 16 — Frontend: componente `FixtureRow`

- [ ] En `frontend/src/components/player/FixtureRow.tsx`, mostrar `fixture.rating` como
      número dorado en el header del row (junto a los pts), usando `var(--gold)`.
- [ ] Solo renderizar si `fixture.rating !== null`.
- [ ] Formato: una cifra decimal fija (ej: `"8.3"`), usando `toFixed(1)`.
- [ ] El badge de rating debe ser visualmente discreto: número pequeño con color gold, sin
      alterar la jerarquía visual existente de pts.

### Paso 17 — Tests

- [ ] Añadir tests unitarios para `MratingFactor` en `tests/domain/` o junto a los tests de
      value objects existentes; cubrir todos los tramos de la tabla (None, <7.0, 7.0–7.9,
      8.0–8.4, >=8.5) y valores de borde (exactamente 7.0, exactamente 8.0, exactamente 8.5).
- [ ] Añadir test de `SFAScoringService.score_match_stats()` que verifica que el rating
      modifica el puntaje esperado.
- [ ] Añadir/actualizar test de `RecalculateScoresUseCase` usando un Fake que incluya `rating`
      en `PlayerStatsEventRecalcRow`; verificar que el delta calculado cambia con rating bajo
      vs rating alto.
- [ ] Los Fakes deben implementar el Protocol completo con el nuevo campo `rating`.

### Paso 18 — Verificación de calidad

- [ ] Ejecutar `pytest tests/` — sin regresiones, coverage ≥ 80%.
- [ ] Ejecutar `flake8 src/ tests/` — sin errores nuevos.
- [ ] Ejecutar `isort --check-only src/ tests/` — sin errores.

---

## Agent Routing Brief

**DDD Designer needed:** yes

El Paso 1 requiere modelado de dominio antes de que comience cualquier otra implementación.
`MratingFactor` es un value object nuevo con invariantes de negocio no triviales:

1. Encapsula una tabla de escala discreta (no es una fórmula matemática continua como M1 o M3)
   que puede evolucionar con las reglas de negocio del producto.
2. El constructor debe rechazar implícitamente cualquier valor fuera de los cuatro factores
   `{0.3, 0.5, 0.75, 1.0}` — garantizando que la lógica de negocio vive en el dominio y
   no se dispersa entre use cases ni repositorios.
3. Sigue el mismo patrón frozen-dataclass con `object.__setattr__` que todos los Mx existentes
   — el DDD Designer debe validar que la implementación es consistente con el resto del
   subdomain de scoring antes de que se escriba el código.

El DDD Designer debe entregar la definición de `MratingFactor` (atributos, constructor,
tabla de escala, patrón de serialización) antes de que comience el Paso 2.

---

## Verificación end-to-end

1. Correr ingesta en un fixture conocido con jugadores con ratings altos y bajos; verificar
   en DB que `player_stats.rating` se pobló correctamente con `SELECT player_id, rating FROM
   player_stats WHERE fixture_id = <id>`.
2. Llamar al endpoint de fixtures por jugador (`GET /api/v1/players/{id}/fixtures`) y verificar
   que el JSON incluye `"rating": 8.3` (o `null`) en cada fixture.
3. Verificar en la UI que el rating dorado aparece en el `FixtureRow` de un jugador con datos.
4. Cambiar manualmente `player_stats.rating` a `6.5` para un jugador de test y ejecutar
   `RecalculateScoresUseCase` para esa competición; verificar que los `pts` del evento STATS
   bajan en comparación con el rating original.
5. Verificar que un jugador con `rating = null` recibe factor `0.5` (no `1.0` — el default
   neutral anterior) y que sus pts de stats disminuyen respecto a la versión anterior.
