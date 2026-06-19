# 0035 — World Cup Beta Close

## Contexto de negocio

El Mundial 2026 está en curso. La beta de SFA está activa con scoring, rankings, detalle de
partido (spec 0030) y cronología de eventos (spec 0033). B1 fue implementado en spec 0034
pero aún no está activado en producción.

Este spec consolida los 15 fixes de cierre que fueron auditados en `CODEX-MUNDIAL-FIXES.md` y
`CODEX-MUNDIAL-EXECUTION-PLAN.md`. El objetivo es cerrar la beta con calidad de producto:
scoring justo para DEL/EXT, explicabilidad del detalle de partido, búsqueda y filtros
completos en el ranking Mundial, sección de países/selecciones, banderas mobile correctas,
click desde el perfil del jugador hacia el partido, y alineaciones sin espejo.

Todo cambio debe especificar si es Mundial-only o global. Los specs 0030, 0033 y 0034 están
implementados; este spec no los repite sino que los extiende donde falta trabajo.

## Restricciones

- `expected_goals` y `expected_assists` no existen como columnas reales en DB. `XG_NO_GOAL` se
  deriva de `shots_on - goals`; `XA_NO_ASSIST` de `passes_key - assists`. No se puede exponer
  "xG real" en ninguna superficie.
- El scoring DEL/EXT con `passes_completed=1` produce piso bajo en partidos sin gol/asistencia.
  Cualquier cambio de base points requiere crear una nueva `ScoringRulesVersion` (v2.3) y
  recalcular — no se modifica la versión activa (id=4) directamente.
- Cambio de base points es `[DDD]` porque toca `BASE_POINTS_TABLE_V2` en `domain/scoring/services.py`
  y `ScoringConfig` en `domain/scoring/value_objects.py`.
- Celery beat actual: 30 minutos. Bajar a 10 minutos durante Mundial requiere cambio en
  `celery_app.py` + env var `INGEST_INTERVAL_MINUTES` configurable. Rollback: restaurar a 30.
- Overrides de posición por selección son riesgo medio-alto: si se aplican sobre la tabla
  `players`, afectan también a los clubes. La solución es un override ligero en capa de
  aplicación (lookup table `WC_POSITION_OVERRIDES`) sin tocar `players.position`.
- Las alineaciones espejadas requieren auditoría primero: el bug puede ser coordenadas API,
  orientación home/away o CSS. No corregir a mano hasta tener diagnóstico.
- La sección "Países/Selecciones" requiere un nuevo endpoint que agregue puntos SFA por
  selección (`team_name` en contexto WC). Requiere nuevo use case + repository query.
- El perfil de selección `GET /wc/teams/{team_external_id}` ya existe parcialmente como
  redirect a `/mundial/seleccion/:id` en frontend (ver `MundialMatchPage.tsx`). El backend
  necesita un endpoint que devuelva goles y puntos SFA totales del equipo en el Mundial.
- Ranking Mundial búsqueda por selección: el `name` actual en `get_ranking` busca solo por
  `player.name` vía `unaccent ILIKE`. Hay que extender para buscar también por `team_name`.
- Banderas faltantes (`worldCupTeams.ts`): Ivory Coast/Curaçao/New Zealand/South Africa/Bosnia
  ya tienen IDs en `WORLD_CUP_TEAM_NAMES_ES` pero NO tienen entradas en `WORLD_CUP_IDENTITIES`
  (que es el mapa de ISO codes para flags). Sin esa entrada, `worldCupTeamFlag()` devuelve `''`.
- La metodología B1 es una página estática en frontend — no requiere nuevo endpoint; solo
  contenido nuevo en la página existente de metodología.
- `PlayerFixture` en `frontend/src/types/index.ts` ya tiene `fixture_id` pero no
  `fixture_external_id` ni `competition_id` (para detectar si es Mundial). Hay que añadirlos
  al DTO de dominio, al schema Pydantic y al tipo TypeScript.
- Temporadas de clubes no visibles en local: este ítem es auditoría, no implementación. El
  spec incluye un checklist de diagnóstico pero no prescribe la solución hasta que se conozca
  la causa raíz.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nueva `ScoringRulesVersion` v2.3 para `passes_completed` DEL=2 EXT=3 | Modificar version activa id=4 | La versión activa tiene scores en producción; cambiarla retroactivamente rompe el historial. Nueva versión permite A/B y rollback sin pérdida de datos. |
| Recálculo obligatorio local con comparativa antes/después antes de producción | Deploy directo | `passes_completed` afecta todos los partidos DEL/EXT del Mundial; hay que ver el impacto cuantitativo antes de subir a VPS. |
| `WC_POSITION_OVERRIDES: dict[int, str]` en use case capa de aplicación (lookup por `player_external_id`) | Columna `wc_position_override` en tabla `players` | Sin tocar la DB ni los clubes. El override vive en código y es reversible. Solo aplica en el contexto del ranking/scoring Mundial (competition_id=350). |
| Extender `name` filter en `get_ranking` para buscar por `player_name OR team_name` | Nuevo parámetro `team` separado | Evita cambios de interfaz API; reutiliza el mismo query param y el frontend no cambia. |
| Nuevo endpoint `GET /wc/teams/standings` con puntos SFA acumulados por selección | Reutilizar `/wc/standings` (puntos de tabla, no SFA) | Los puntos de tabla son de la competición oficial; los puntos SFA son del sistema propio. Son datos diferentes que no deben mezclarse. |
| Nuevo endpoint `GET /wc/teams/{team_external_id}` para perfil de selección | Construir perfil desde el frontend con múltiples calls | Un endpoint dedicado permite caché Redis y mantiene la arquitectura hexagonal. |
| `INGEST_INTERVAL_MINUTES` como env var con default=30 | Hardcodear 10 en celery_app.py | Permite volver a 30 post-Mundial sin rebuild; rollback = cambiar env var y reiniciar worker. |
| Añadir `fixture_external_id` y `competition_id` al `PlayerFixtureDTO` y schema existentes | Nuevo endpoint `/players/{id}/wc-fixtures` | El DTO ya existe; añadir campos es additive y backward-compatible. El frontend solo los usa si `competition_id == 350`. |
| Fix de banderas en `worldCupTeams.ts`: añadir entradas faltantes en `WORLD_CUP_IDENTITIES` | Nuevo componente de flags | El mapa ya existe y funciona; solo le faltan 5 entradas. Un parche quirúrgico es suficiente. |
| Explicabilidad del detalle de partido en frontend: enriquecer `PlayerFixture` con `m1_label`, `is_away`, `rival_stronger` | Nuevo endpoint separado | El endpoint `GET /players/{id}/fixtures` ya devuelve `m1`, `m2`, `m3`, `m4`, `mvisit`; solo falta exponerlos en UI con labels humanos. No se necesita dato nuevo desde backend. |
| No implementar alineaciones espejadas hasta auditoría diagnóstica | Fix inmediato CSS | El bug puede venir de múltiples fuentes. Prescribir un fix sin diagnóstico puede empeorar otras selecciones. |
| Temporadas clubes: solo checklist de diagnóstico, no fix | Fix asumido | La causa raíz es desconocida. El spec provee el árbol de diagnóstico; la implementación del fix queda para un spec posterior si es necesario. |
| Metodología B1: solo frontend (contenido estático) | Nuevo endpoint | No hay lógica de backend nueva; es documentación en una página ya existente. |
| Sección "países" con click a perfil de selección existente (`/mundial/seleccion/:id`) | Nueva ruta | La ruta ya existe en `MundialMatchPage.tsx` y `worldCupTeamName` ya mapea nombres. Solo falta la sección visual y el endpoint de ranking de selecciones. |

## Domain Model

B1 está implementado en `domain/scoring/value_objects.py` (spec 0034). Este spec no introduce
nuevas entidades de dominio propias — solo extiende DTOs existentes y añade queries de
agregación.

### Cambios en DTOs existentes

**`PlayerFixtureDTO`** — en `domain/ports.py` (o donde viva actualmente):
Añadir campos `fixture_external_id: int | None` y `competition_id: int | None`.
Ambos con default `None` para backward-compat.

**`WcTeamSFARankingDTO`** — nuevo DTO frozen en `domain/world_cup_ports.py`:
```python
@dataclass(frozen=True)
class WcTeamSFARankingDTO:
    team_external_id: int
    team_name: str
    total_sfa_pts: float
    total_goals: int       # sum of goals from player_stats for this team in WC
    player_count: int      # players with at least 1 minute
    rank: int
```

**`WcTeamProfileDTO`** — nuevo DTO frozen en `domain/world_cup_ports.py`:
```python
@dataclass(frozen=True)
class WcTeamProfileDTO:
    team_external_id: int
    team_name: str
    total_sfa_pts: float
    total_goals: int
    fixtures: list[WorldCupFixtureDTO]   # partidos del equipo
    top_players: list[RankedPlayerDTO]   # top 5 jugadores por SFA pts
```

### Ubicación en domain/

- `src/sfa/domain/world_cup_ports.py` — añadir `WcTeamSFARankingDTO` y `WcTeamProfileDTO`
- `src/sfa/domain/ports.py` — añadir campos a `PlayerFixtureDTO`

## Integraciones externas

- **API-Football**: no se añaden nuevos requests en este spec. La cronología (0033) y el
  enrichment de birth_dates (0034) ya cubren los endpoints relevantes. El perfil de selección
  usa datos de DB (sfa_season_scores + player_stats) sin API calls adicionales.
- **Celery Beat**: se modifica el schedule para usar `INGEST_INTERVAL_MINUTES` env var.
  No se añaden nuevas tasks al beat.
