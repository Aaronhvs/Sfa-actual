# 0034 — B1 Age Exceptionality Bonus

## Contexto de negocio

El sistema SFA actualmente puntúa todas las contribuciones ofensivas (goles y asistencias)
con la misma fórmula base, sin reconocer el mérito excepcional de que un jugador muy joven
(17–20 años) o veterano (35+) anote o asista en un partido de alto nivel. Esta feature
introduce un bonus aditivo **B1** que se suma al score SFA por partido cuando se cumplen
las condiciones de edad al día exacto del partido.

La fórmula total pasa de:

```
total_pts = BASE_PTS × M1 × M2 × M3 × M4 × Mvisit
```

a:

```
total_pts = BASE_PTS × M1 × M2 × M3 × M4 × Mvisit + B1
```

B1 se aplica **por partido** sobre el total de goles + asistencias del jugador en ese fixture,
con un cap de 3 contribuciones:

| Contribuciones en el partido | B1 |
|---|---|
| 1 (gol o asistencia) | +200 pts |
| 2 | +400 pts |
| 3+ (cap) | +600 pts |

Solo aplica a `GOAL`, `GOAL_PENALTY`, `ASSIST`, `CORNER_ASSIST`. No aplica a `GOAL_SHOOTOUT`
(tanda de penales — contexto artificial, no mérito técnico en el juego).

**Por qué ahora:** el Mundial 2026 está en curso con jugadores jóvenes como Lamine Yamal,
Endrick y veteranos icónicos activos. El bonus da relevancia editorial al sistema SFA en
un momento de alta exposición.

## Restricciones

- `birth_date` no existe en la tabla `players` — hay que añadirlo como columna nullable.
- La edad se calcula con fecha exacta (`birth_date` vs `fixture.played_at`), **no** con
  `player.age` de la API (que es la edad al momento del fetch, no al partido).
- API-Football provee `birth.date` en `YYYY-MM-DD` en el endpoint
  `/players?team={team_id}&season={season}`. Este endpoint devuelve todos los jugadores del
  squad en un solo request — batching óptimo (1 request por equipo, no por jugador).
- Quota API-Football: 7500 req/día. El enrichment debe ser por equipo, nunca por jugador
  individual. No se puede ejecutar dentro del loop de ingestion sin análisis de impacto.
- B1 debe ser controlable por versión de reglas (`ScoringConfig`): activable/desactivable
  y con parámetros configurables (rangos de edad, tabla de bonus).
- Los scores históricos calculados con reglas anteriores (sin B1) no deben cambiar
  automáticamente. El recálculo con B1 activo es un proceso explícito.
- Celery Beat ingesta el Mundial cada 30 min — el enrichment de `birth_date` no debe
  bloquear ni interferir con esa pipeline.
- `ingest_competition` no debe tocar `birth_date` — separación de responsabilidades.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| `birth_date DATE nullable` en tabla `players` | Nueva tabla `player_birth_dates` | La fecha de nacimiento es un atributo estable del jugador, no un snapshot temporal. Una tabla separada solo añade joins sin beneficio. Nullable permite rollout incremental. |
| Enrichment task separada `enrich_player_birth_dates_task` | Enriquecer `birth_date` dentro de `ingest_competition` | `ingest_competition` ya es costosa en API quota (fixtures/events/players). Añadir `/players?team=...` dentro del loop duplicaría requests. El enrichment es una operación one-shot o periódica, no por-partido. Además, no rompe la pipeline del Mundial. |
| Endpoint `/players?team={team_id}&season={season}` (batch por equipo) | `/players?id={player_id}&season={year}` (por jugador) | El endpoint por equipo devuelve todo el squad en 1 request. El endpoint por jugador requeriría N requests (miles de jugadores). Diferencia de 10x–100x en quota consumida. |
| B1 calculado en `CalculateScoresForRulesVersionUseCase._score_individual_event()` | Use case separado `CalculatB1BonusUseCase` | B1 es una modificación de la función de scoring de eventos individuales, no un bonus de fase (como los achievement bonuses). Pertenece al mismo pipeline de cálculo por evento. Separarlo duplica código y rompe atomicidad. |
| B1 como campo aditivo en `PlayerEventScore.final_points` (sumado al total de la sesión de scoring) | Columna separada `b1_bonus` en `player_event_scores` | B1 se suma al `final_points` del evento, igual que el midfield bonus se suma al `final_points` del stats event. No necesita columna propia; el `calculation_details` JSONB ya auditea el desglose. |
| B1 agrupado por fixture dentro del use case antes de distribuir | Calcular B1 por cada evento individual (goal/assist) independientemente | La regla es "contribuciones totales en el partido" — hay que contar primero cuántos goals+assists tiene el jugador en el fixture, luego asignar el bonus. Esto requiere agrupar por (player_id, fixture_id) antes de distribuir B1 entre los eventos del fixture. |
| Distribuir B1 equitativamente entre los N eventos del fixture | Asignar todo B1 al primer evento del fixture | Distribución equitativa evita distorsiones en el `calculation_details` por evento. Total de `final_points` es el mismo en ambos casos. |
| `b1_enabled: bool` + `b1_young_max_age`, `b1_veteran_min_age`, `b1_bonus_table` en `ScoringConfig` | Flag global fuera del config | Consistente con el patrón existente (ej. `enable_midfield_control_bonuses`). Permite versionar B1 junto con el resto de reglas. Activar B1 requiere crear una nueva `ScoringRulesVersion` — el historial de scores anteriores queda intacto. |
| `birth_date` propagado en `PlayerEventRawContextDTO` con campo nuevo `player_birth_date: date \| None` | Lookup de `birth_date` dentro del use case de scoring | El scoring use case solo puede importar de `domain/` — no puede importar ORM models. La fecha debe llegar en el DTO que ya construye el repository. |
| `EnrichPlayerBirthDatesUseCase` con `BirthDateEnrichmentRepositoryPort` + `PlayerBirthDateProviderPort` | Enriquecer directamente desde el repository | Arquitectura hexagonal: el use case orquesta, el provider fetcha la API, el repo escribe en DB. Igual que el patrón de ingestion. |
| Rollout en 3 fases: (1) migración + enrich, (2) nueva `ScoringRulesVersion` con B1 activo, (3) recálculo explícito | Activar B1 automáticamente en la versión activa | Las fases separadas permiten verificar datos de `birth_date` antes de recalcular, y dan control total al operador sobre cuándo el cambio afecta los scores visibles. |
| No aplicar B1 a `GOAL_SHOOTOUT` | Aplicar B1 a todos los goal types incluyendo shootout | Los penales en tanda son un contexto artificial (sorteo de suerte). El mérito del jugador joven/veterano es en el juego real, no en la tanda. |

## Domain Model

B1 no requiere nuevas entidades de dominio con invariantes propias. Es una extensión
del scoring de eventos individuales. Los cambios son:

### Value objects nuevos

**`B1AgeExceptionalityBonus`** — en `domain/scoring/value_objects.py`

```python
@dataclass(frozen=True)
class B1AgeExceptionalityBonus:
    """Additive bonus for exceptional age (young or veteran) in goal/assist contributions.

    contributions: total goals + assists by player in the fixture (capped at 3).
    bonus_pts: B1 total for the fixture (to be distributed evenly across N events).
    """
    value: float  # total B1 for the fixture

    def __init__(
        self,
        contributions: int,
        player_birth_date: date | None,
        fixture_date: date,
        config: ScoringConfig,
    ) -> None:
        if not config.b1_enabled or player_birth_date is None:
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

Función auxiliar `_age_at_date(birth_date: date, reference_date: date) -> int` en el mismo
archivo — calcula edad exacta en años completos al día de referencia.

### Cambios en `ScoringConfig`

Nuevos campos opcionales (default = backward-compatible, B1 desactivado):

```python
b1_enabled: bool = False
b1_young_min_age: int = 17
b1_young_max_age: int = 20
b1_veteran_min_age: int = 35
b1_bonus_table: dict[int, int] = field(default_factory=dict)
# default: {1: 200, 2: 400, 3: 600}
```

`from_dict` y `to_dict` deben serializar/deserializar estos campos.

### Cambios en `PlayerEventRawContextDTO`

Nuevo campo en `domain/scoring_ports.py`:

```python
player_birth_date: date | None = None   # DATE from players.birth_date
fixture_date: date | None = None        # DATE extracted from fixture.played_at
```

### Ubicación en domain/

- `src/sfa/domain/scoring/value_objects.py` — `B1AgeExceptionalityBonus`, `_age_at_date`, nuevos campos en `ScoringConfig`
- `src/sfa/domain/scoring_ports.py` — `player_birth_date` y `fixture_date` en `PlayerEventRawContextDTO`

## Integraciones externas

**API-Football v3** — endpoint `/players`

- Parámetros: `team={team_id}&season={season}`
- Campo relevante: `response[*].player.birth.date` → string `"YYYY-MM-DD"`
- Fallback: si `birth.date` es `null` o ausente, guardar `None` en DB (nullable).
- Rate limiting: mismo mecanismo de retry/backoff que tiene el provider actual.
- Quota: 1 request por equipo por season. Para ~20 equipos × ~20 competiciones = ~400 requests
  para enriquecer toda la DB. Aceptable dentro de 7500/día.
- El provider nuevo `fetch_squad_birth_dates(team_id, season)` retorna
  `list[PlayerBirthDateRawDTO]` con `(external_id: int, birth_date: date | None)`.
