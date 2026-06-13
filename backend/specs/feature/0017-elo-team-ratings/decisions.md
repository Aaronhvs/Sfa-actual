# 0017 — ELO Team Ratings

## Contexto de negocio

El multiplicador M1 (dificultad del rival) depende actualmente de `team_strengths`, que se
deriva de la posición en la tabla de liga. Este mecanismo tiene dos problemas graves:

1. **Lag de información:** un equipo recién ascendido que gana sus primeros partidos sigue
   apareciendo como débil porque la tabla acumulada aún no refleja su rendimiento real.
2. **Aproximación gruesa:** la posición en tabla es un proxy pobre de la verdadera
   dificultad del rival en un partido puntual — no distingue entre un 3er lugar de la
   Premier League y un 3er lugar de la Eredivisie.

La solución es reemplazar la strength derivada de standings por un **rating ELO propio**,
inicializado con datos históricos reales de ClubElo (http://api.clubelo.com) y actualizado
partido a partido. Esto produce strengths más precisos en tiempo real y captura la forma
actual del equipo.

## Restricciones

- ClubElo API es pública, sin autenticación, responde CSV. No tiene SLA garantizado —
  se usa solo en el seed one-time y no en el hot-path de ingesta.
- Los ELO de ClubElo van de ~1500 (débiles) a ~2100 (élite). Deben normalizarse al rango
  0–100 que usa `TeamStrengthBlend` y `M1RivalDifficulty`.
- La tabla `team_strengths` tiene `CHECK(strength BETWEEN 0 AND 100)` y
  `CHECK(source IN ('calculated', 'default', 'override'))` — ambas constraints deben
  ampliarse sin romperse hacia atrás.
- El modelo `TeamStrength` tiene una unique constraint `uq_team_strength` por
  `(team_id, season, competition_id)`. Con ELO, la strength es **global** (no por
  competición), pero el scoring la lee por competición. Se resolverá con una columna
  `elo_raw` adicional y semántica de "misma strength para todas las competiciones del
  equipo en esa temporada".
- El nombre de los equipos en ClubElo difiere del nombre en SFA — se requiere mapping
  estático más fuzzy fallback.
- `TeamStrengthRepositoryPort` vive en `domain/scoring_ports.py` — solo puede ser
  extendido, no modificado de manera breaking.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Guardar ELO bruto en columna `elo_raw NUMERIC(7,2)` en `team_strengths` y ELO normalizado en `strength` | Tabla separada `team_elo_ratings` | Evita JOIN adicional en el hot-path de scoring; `strength` sigue siendo la columna canónica que lee M1 |
| Normalización: `normalized = (elo - 1400) / 700 * 100`, clampeado 0–100 | Normalización dinámica (min/max del snapshot) | Determinista y reproducible; no depende del snapshot actual; ELO_FLOOR=1400, ELO_RANGE=700 cubre el rango observado con margen |
| Factor K por tipo de competición hardcodeado en `EloCalculatorService` con dict `competition_id → K` configurable vía parámetro | Almacenado en `ScoringConfig` | ScoringConfig es inmutable y versionada; el K factor es operacional, no una regla de scoring histórica. Se pasa como argumento al use case |
| Mapping ClubElo ↔ SFA: dict estático `CLUBELO_NAME_MAP` en el provider + fuzzy fallback con `difflib.get_close_matches` (cutoff 0.75) | Tabla `clubelo_name_mappings` en DB | El dict estático es suficiente para las diferencias conocidas (< 20 equipos problemáticos); no justifica migraciones DB |
| Seed de ClubElo via endpoint admin `POST /admin/elo/seed` con `date` param | Script one-time | Permite re-seed sin acceso SSH; el endpoint es protegido por API key interna |
| ELO propio calculado cruzando **todos** los fixtures de la temporada ordenados por `played_at`, sin filtrar por competición | Calcular ELO separado por competición | Un equipo tiene un solo ELO global; mezclarlo con partidos de copa refleja mejor la forma real |
| La strength se almacena **por (team_id, season, competition_id)** aunque el ELO sea global — misma `strength` replicada para todas las competiciones del equipo en esa temporada | Cambiar la clave de `team_strengths` a solo `(team_id, season)` | Evita migración breaking de la unique constraint y mantiene compatibilidad con `TeamStrengthRepositoryPort.get_team_strength(team_id, season, competition_id)` |
| Equipos sin seed ELO usan `source='calculated'` (standings-based) como fallback | Strength=50 fija | Preserva el comportamiento actual para equipos no cubiertos por ClubElo (divisiones inferiores, copas con equipos amateur) |
| Auto-update ELO se dispara como `apply_elo_update_task` desde `_run_ingest_competition` después del commit | Hook dentro del use case de ingesta | Las tasks no deben anidar lógica de dominio; el task de ingesta ya dispara `calculate_all_scores_task`, este sigue el mismo patrón |
| `source` en `team_strengths` amplía el CHECK a: `'calculated', 'default', 'override', 'clubelo_seed', 'elo_v1'` | Valores genéricos | Trazabilidad — permite saber qué filas vienen de ELO vs standings |

## Domain Model

No se requiere DDD Designer. No se crean nuevas entidades de dominio:

- `EloRating` es un simple value object (float) sin invariantes de negocio complejas —
  se encapsula directamente en `EloCalculatorService`.
- No hay aggregate raíz nuevo — el aggregate existente es `TeamStrength` en infra.
- El port `TeamStrengthRepositoryPort` se extiende con dos métodos nuevos (non-breaking).

### Value Objects nuevos

**Ninguno en `domain/`**. La normalización ELO es una función pura en `EloCalculatorService`
(infra), no un value object de dominio porque no tiene invariantes de negocio que proteger
más allá del clamp 0–100 que ya hace `TeamStrengthBlend`.

### Extensiones a `scoring_ports.py`

```python
# Métodos adicionales en TeamStrengthRepositoryPort:

async def get_team_strength_with_elo(
    self, team_id: int, season: str, competition_id: int
) -> tuple[float | None, float | None]: ...
# Returns: (normalized_strength, elo_raw)

async def upsert_team_elo(
    self,
    team_id: int,
    season: str,
    elo_raw: float,
    strength_normalized: float,
    source: str,           # 'clubelo_seed' | 'elo_v1'
    competition_ids: list[int],  # replica en todas las competiciones activas del equipo
) -> None: ...

async def get_all_teams_with_elo(self, season: str) -> list[TeamEloRow]: ...
# Devuelve todos los equipos con elo_raw para ordenar fixtures cronológicamente

async def get_fixtures_for_elo_recalc(
    self, season: str, competition_ids: list[int]
) -> list[FixtureEloRow]: ...
# Todos los fixtures finalizados, ordenados por played_at ASC
```

### DTOs de dominio nuevos

```python
@dataclass(frozen=True)
class TeamEloRow:
    team_id: int
    season: str
    elo_raw: float          # ELO actual (1400-2100)
    strength: float         # normalizado 0-100

@dataclass(frozen=True)
class FixtureEloRow:
    fixture_id: int
    home_team_id: int
    away_team_id: int
    played_at: datetime
    competition_id: int
    home_goals: int
    away_goals: int
    season: str
```

## Integraciones externas

### ClubElo API

- **URL snapshot:** `GET http://api.clubelo.com/{YYYY-MM-DD}` → CSV sin cabecera con
  campos `Rank,Club,Country,Level,Elo,From,To`
- **URL historial:** `GET http://api.clubelo.com/{TeamName}` → CSV historial completo
- **Autenticación:** ninguna
- **Rate limit:** no documentado — usar solo en seed one-time, no en hot-path
- **Timeout:** 30s por request
- **Fallback:** si ClubElo no responde durante el seed, el endpoint devuelve HTTP 503 y
  el operador puede reintentar

### Name mapping conocido (ClubElo → nombre normalizado para match con SFA)

```python
CLUBELO_NAME_MAP: dict[str, str] = {
    "Paris SG": "Paris Saint-Germain",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Atletico": "Atletico Madrid",
    "Sociedad": "Real Sociedad",
    "Bilbao": "Athletic Club",
    "Dortmund": "Borussia Dortmund",
    "Leverkusen": "Bayer Leverkusen",
    "Gladbach": "Borussia Monchengladbach",
    "Wolfsburg": "Wolfsburg",
    "Hannover": "Hannover 96",
    "Koln": "FC Koln",
    "Nurnberg": "FC Nurnberg",
    "Frankfurt": "Eintracht Frankfurt",
    "Schalke": "Schalke 04",
    "Stuttgart": "VfB Stuttgart",
    "Hertha": "Hertha Berlin",
    "Newcastle": "Newcastle United",
    "Brighton": "Brighton & Hove Albion",
    "Spurs": "Tottenham Hotspur",
    "Wolves": "Wolverhampton Wanderers",
    "Leicester": "Leicester City",
    "Nottm Forest": "Nottingham Forest",
    "Sheffield Utd": "Sheffield United",
    "Luton": "Luton Town",
    "Burnley": "Burnley",
    "Brentford": "Brentford",
    "Fulham": "Fulham",
    "Bournemouth": "Bournemouth",
    "Sevilla": "Sevilla",
    "Villarreal": "Villarreal",
    "Betis": "Real Betis",
    "Celta": "Celta Vigo",
    "Osasuna": "Osasuna",
    "Getafe": "Getafe",
    "Almeria": "Almeria",
    "Girona": "Girona",
    "Las Palmas": "Las Palmas",
    "Alaves": "Deportivo Alaves",
    "Vallecano": "Rayo Vallecano",
    "Cadiz": "Cadiz",
    "Udinese": "Udinese",
    "Monza": "Monza",
    "Frosinone": "Frosinone",
    "Cagliari": "Cagliari",
    "Salernitana": "Salernitana",
    "Verona": "Hellas Verona",
    "Lecce": "Lecce",
    "Genoa": "Genoa",
    "Empoli": "Empoli",
    "Sassuolo": "Sassuolo",
    "Spezia": "Spezia",
    "Cremonese": "Cremonese",
    "Lens": "RC Lens",
    "Rennes": "Stade Rennais",
    "Marseille": "Olympique de Marseille",
    "Lyon": "Olympique Lyonnais",
    "Lille": "LOSC Lille",
    "Nantes": "FC Nantes",
    "Nice": "OGC Nice",
    "Strasbourg": "RC Strasbourg",
    "Montpellier": "Montpellier HSC",
    "Reims": "Stade de Reims",
    "Metz": "FC Metz",
    "Lorient": "FC Lorient",
    "Brest": "Stade Brestois",
    "Clermont": "Clermont Foot",
    "Ajaccio": "AC Ajaccio",
    "Auxerre": "AJ Auxerre",
    "Toulouse": "Toulouse FC",
    "RB Leipzig": "RB Leipzig",
    "Augsburg": "FC Augsburg",
    "Freiburg": "SC Freiburg",
    "Hoffenheim": "TSG 1899 Hoffenheim",
    "Mainz": "1. FSV Mainz 05",
    "Bochum": "VfL Bochum",
    "Heidenheim": "1. FC Heidenheim",
    "Darmstadt": "SV Darmstadt 98",
    "Union Berlin": "Union Berlin",
    "Werder": "Werder Bremen",
}
```
