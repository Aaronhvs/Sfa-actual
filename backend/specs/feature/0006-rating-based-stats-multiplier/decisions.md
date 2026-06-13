# Rating-Based Stats Multiplier (Mrating)

## Contexto de negocio

SFA calcula puntos por dos caminos: eventos individuales (goles, asistencias) que usan los
cinco multiplicadores M1×M2×M3×M4×Mvisit, y stats de partido (duelos, regates, tackles, etc.)
que actualmente usan solo M1. El problema detectado es que las stats acumulativas se acumulan
durante 40+ partidos sin importar si esas acciones impactaron realmente el resultado: un lateral
puede acumular muchos puntos de stats en partidos donde su equipo perdió y él no fue determinante.

La solución aprobada es introducir un factor de escala basado en el rating que API-Football
asigna a cada jugador por partido (`games.rating` en `fixtures/players`). Dicho rating ya se
obtiene en la ingesta actual pero se descarta — este spec lo rescata, lo persiste y lo aplica
al multiplicador de stats.

## Restricciones

- El rating llega como string o `null` desde API-Football (ej: `"7.5"`, `"8.2"`, `null`).
- El campo debe almacenarse como `Float nullable` en `player_stats`; nunca bloquea la ingesta.
- El factor solo se aplica al camino `score_match_stats()` — los eventos individuales
  (goles/asistencias) no se ven afectados.
- La fórmula de stats pasa de `combined = max(0.3, min(4.0, m1))` a
  `combined = max(0.3, min(4.0, m1 * mrating))`.
- El clamping externo [0.3, 4.0] se mantiene idéntico.
- El frontend debe mostrar el rating por partido en `FixtureRow` y en el perfil del jugador
  usando el número dorado estilo "8.3".
- La columna nueva en `player_stats` requiere una migración Alembic.
- `RecalculateScoresUseCase` debe leer `rating` desde `PlayerStatsEventRecalcRow` y aplicar
  `MratingFactor` para no divergir de la ingesta.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nuevo value object `MratingFactor` en `domain/scoring/value_objects.py` | Función libre o constante en el use case | Consistencia con el patrón existente M1–Mvisit; encapsula invariantes en dominio |
| Persistir `rating` en `player_stats.rating` (Float nullable) | Columna en tabla aparte o calcularlo on-the-fly | La recalculación necesita el dato; la tabla `player_stats` ya tiene la clave (player, fixture) |
| `rating` en `PlayerStatsRawDTO` como campo opcional con default `None` | Nuevo DTO | Mantener la firma del Port sin romper implementaciones existentes; es un campo del mismo recurso |
| Pasar `rating: float | None` directamente a `score_match_stats()` | Resolver en el scoring service internamente | Hace la firma explícita y testeable; el service no debe acceder a infra |
| Columna `rating` en `PlayerFixtureDTO` y `PlayerFixture` (frontend type) | Solo mostrarlo desde los eventos | El componente `FixtureRow` ya recibe `fixture: PlayerFixture`; extenderlo es la ruta mínima |
| Alembic migration para añadir columna nullable sin default server | `ALTER TABLE` manual | Reproducibilidad del esquema entre entornos |
| El factor Mrating se multiplica por M1 antes del clamp externo | Clamp intermedio o nuevo clamp propio | El clamp [0.3, 4.0] ya existe; añadir otro nivel sería redundante e inconsistente |

## Domain Model

### Value object nuevo: `MratingFactor`

**Ubicación:** `src/sfa/domain/scoring/value_objects.py`

**Atributos:**
- `value: float` — factor resultante (read-only, frozen dataclass)

**Reglas de construcción (tabla de escala aprobada):**

| Condición sobre `rating` | `value` resultante |
|---|---|
| `None` (sin dato de API) | `0.5` |
| `rating < 7.0` | `0.3` |
| `7.0 <= rating < 8.0` | `0.5` |
| `8.0 <= rating < 8.5` | `0.75` |
| `rating >= 8.5` | `1.0` |

**Invariantes:**
- El constructor recibe `rating: float | None`.
- `value` siempre cae en `{0.3, 0.5, 0.75, 1.0}` — nunca otro valor.
- Si `rating` es un string válido de la API, la conversión a `float` ocurre en la capa de
  infra (provider) antes de llegar al value object; el domain recibe `float | None`.
- El value object es frozen (`dataclass(frozen=True)`) al igual que todos los demás Mx.

**Ubicación propuesta en domain/:**
- `src/sfa/domain/scoring/value_objects.py` — añadir clase `MratingFactor` junto a las clases
  `M1RivalDifficulty`, `M2CompetitionStage`, etc. ya existentes.

## Integraciones externas

- **API-Football v3 — `fixtures/players`:** el campo `games.rating` ya se consume en
  `APIFootballProvider.fetch_fixture_players()` pero actualmente se descarta. Valor esperado:
  string numérico (`"7.5"`) o `null`. La conversión `str → float` se hace en el provider con
  manejo de excepciones; `null` y errores de conversión producen `None`.
- No hay nuevas llamadas a la API; el dato ya se obtiene en la misma request existente.
- Rate limit: sin impacto (misma request, misma cuota).
