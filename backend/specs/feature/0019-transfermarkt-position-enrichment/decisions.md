# Spec 0019 — Transfermarkt Position Enrichment

## Contexto de negocio

La tabla `players` tiene ~5,837 jugadores en posición MC (97%), incluyendo laterales,
mediocampistas defensivos y de ataque mal clasificados. API-Football solo provee 4 posiciones
genéricas ("Goalkeeper", "Defender", "Midfielder", "Attacker"), mientras que Transfermarkt
provee posiciones granulares ("Centre-Back", "Right-Back", "Attacking Midfield", etc.).

El spec 0018 aplicó un guard de "no sobrescribir con MC", pero no resolvió la fuente de
verdad: los jugadores ya clasificados erróneamente siguen en MC, y no existe mecanismo para
distinguir una posición asignada por TM (confiable) de una asignada por API-Football
(genérica) o heurística.

Este spec implementa Transfermarkt como fuente canónica de posiciones, con:
- Un scraper HTTP que obtiene la posición granular de TM por jugador
- Una tabla de mapeo `player_tm_ids` para persistir la equivalencia de IDs
- Un campo `position_source` en `players` que controla la prioridad de escritura
- Un nuevo valor de posición `MCO` (Attacking Midfield) con su tabla de puntos propia
- Un use case batch que enriquece posiciones con rate limiting respetuoso (1 req/seg)

## Restricciones

- Sin BeautifulSoup en el scraper de TM: parsear HTML con regex (sin dependencias nuevas)
- Transfermarkt no comparte IDs con API-Football: se requiere name-matching + tabla de mapeo
- Rate limit TM: maximo 1 req/seg (politica de scraping educado)
- La posicion `transfermarkt` nunca puede ser sobreescrita por ingestas futuras de API-Football
- No re-ingestar fixtures historicos (cuota 7,500 req/dia insuficiente)
- MCD (Defensive Midfield) se mapea a MC existente — no se crea grupo separado
- MCO (Attacking Midfield) SI se crea como nuevo Position enum + nuevo PositionGroup
- El enum Position en PostgreSQL es `native_enum=False` (VARCHAR): ALTER TABLE sin DROP/RECREATE

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Crear MCO como nuevo valor en Position enum y PositionGroup | Mapear a EXT o MF | MCO tiene perfil de scoring propio: mas goles que MF, menos defensa, mas xA |
| MCD mapea a MC | Crear MCD como nuevo grupo | Evita fragmentacion; MCD ya recibe scoring de MF que es apropiado |
| `position_source` como VARCHAR(20) NOT NULL DEFAULT 'apifootball' | Enum PostgreSQL | VARCHAR es mas simple de migrar y extender |
| Tabla `player_tm_ids` separada de `players` | Columna `tm_id` en players | Mantiene players limpio; el mapeo TM es opcional y puede fallar |
| Busqueda TM via schnellsuche endpoint + nombre+equipo | API publica de TM (no existe) | Scraping del endpoint de busqueda es el unico metodo disponible |
| Batch enrichment como Celery task separado | Sincronico en el endpoint | El proceso puede tomar horas para ~6000 jugadores a 1 req/seg |
| Prioridad de fuente en `upsert_player` a nivel de infra (repository) | Guard solo en use case | Debe ser imposible de bypassear: la proteccion pertenece a la capa que escribe |
| MCO passes_avg=35 en `_DEFAULT_PASSES_AVG_V2` | Heredar de MF (50) | MCO circula menos que MC puro; umbral 35 es realista para mediapuntas |
| `asyncio.sleep(1.0)` en el use case, NO en el scraper | Sleep dentro de `_get_html` | Los tests con Fakes no deben ser lentos; el rate-limit es responsabilidad del caller |

## Domain Model

### Position enum — nuevo valor

```python
MCO = "MCO"  # Attacking Midfield / Mediocampista ofensivo
```

### PositionGroup enum — nuevo valor

```python
MCO = "MCO"  # Attacking Midfield / Mediapunta
```

### position_to_group — actualizacion

```python
Position.MCO: PositionGroup.MCO,
```

### BASE_POINTS_TABLE_V2 — nueva fila MCO

Razonamiento: MCO marca mas goles que MC puro (umbral GOAL 600 vs 700 de MC porque el
denominador de rareza es menor), pasa menos (PASSES threshold 35 vs 50), defiende menos
(TACKLES 45, INTERCEPTIONS 60), y crea mas oportunidades (XA_NO_ASSIST 80).

```python
PositionGroup.MCO: {
    ActionType.GOAL: 600,
    ActionType.GOAL_PENALTY: 320,
    ActionType.GOAL_SHOOTOUT: 320,
    ActionType.ASSIST: 520,
    ActionType.CORNER_ASSIST: 270,
    ActionType.XG_NO_GOAL: 65,
    ActionType.XA_NO_ASSIST: 80,
    ActionType.DRIBBLES_WON: 90,
    ActionType.DUELS_WON: 8,
    ActionType.TACKLES: 45,
    ActionType.INTERCEPTIONS: 60,
    ActionType.BLOCKS: 70,
    ActionType.FOULS_DRAWN: 35,
    ActionType.PASSES_COMPLETED: 3,
    ActionType.FOULS_COMMITTED: -20,
    ActionType.YELLOW_CARD: -120,
    ActionType.RED_CARD: -500,
    ActionType.PENALTY_WON: 200,
    ActionType.DRIBBLES_PAST: -20,
}
```

### _DEFAULT_PASSES_AVG_V2 — actualizacion

```python
"MCO": 35,
```

### DTOs de dominio nuevos (en `domain/transfermarkt_ports.py`)

```python
@dataclass(frozen=True)
class TmPlayerData:
    tm_id: int
    position_raw: str      # "Central Midfield", "Right-Back", etc.
    position_mapped: Position  # SFA enum mapeado

@dataclass(frozen=True)
class TmSearchResult:
    tm_id: int
    name: str
    team_name: str
    slug: str              # slug para construir la URL de perfil

@dataclass(frozen=True)
class PlayerTmIdRow:
    player_id: int
    tm_id: int
    verified: bool

@dataclass(frozen=True)
class PlayerForEnrichDTO:
    id: int
    name: str
    team_name: str
    position_source: str

@dataclass(frozen=True)
class EnrichPositionsResult:
    total_processed: int
    matched: int
    position_updated: int
    unmatched: int
    failed: int
    skipped_already_tm: int
```

### Ports (Protocols) nuevos (en `domain/transfermarkt_ports.py`)

```python
@runtime_checkable
class TransfermarktProviderPort(Protocol):
    async def fetch_player_position(self, tm_id: int, slug: str) -> TmPlayerData | None: ...
    async def search_player(self, name: str, team_name: str) -> TmSearchResult | None: ...

@runtime_checkable
class PlayerTmIdRepositoryPort(Protocol):
    async def get_tm_id(self, player_id: int) -> PlayerTmIdRow | None: ...
    async def upsert_tm_id(self, player_id: int, tm_id: int, verified: bool) -> None: ...

@runtime_checkable
class EnrichPositionRepositoryPort(Protocol):
    async def get_players_without_tm_source(self, limit: int) -> list[PlayerForEnrichDTO]: ...
    async def update_player_position(
        self, player_id: int, position: Position, source: str,
    ) -> None: ...
```

### Mapping Transfermarkt → SFA Position

```python
TM_POSITION_MAP: dict[str, Position] = {
    "Goalkeeper":         Position.GK,
    "Centre-Back":        Position.DC,
    "Right-Back":         Position.LAT,
    "Left-Back":          Position.LAT,
    "Right Midfield":     Position.LAT,  # carrilero
    "Left Midfield":      Position.LAT,  # carrilero
    "Defensive Midfield": Position.MC,
    "Central Midfield":   Position.MC,
    "Attacking Midfield": Position.MCO,
    "Right Winger":       Position.EXT,
    "Left Winger":        Position.EXT,
    "Second Striker":     Position.EXT,
    "Centre-Forward":     Position.DEL,
    "Striker":            Position.DEL,
    "Forward":            Position.DEL,
}
```

## Integraciones externas

**Transfermarkt** — scraping HTTP directo:
- Perfil: `https://www.transfermarkt.com/{slug}/profil/spieler/{tm_id}` (GET sin auth)
- Busqueda: `https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={name}&x=0&y=0`
- User-Agent normal de navegador, sin cookies, sin tokens
- Rate limit autoimpuesto: 1 req/seg en el use case
- Timeout: 30s por request
- Fallback en 404 o timeout: None (sin excepcion al caller)
- Confirmado funcionando en pruebas manuales (Vitinha 388282, Bruno Fernandes 240306, Van Dijk 139208, Trent 314353, Bellingham 581678)

## Archivos afectados

| Archivo | Cambio |
|---|---|
| `infrastructure/models/enums.py` | Agregar MCO a Position |
| `infrastructure/models/players/models.py` | Agregar columna position_source VARCHAR(20) |
| `domain/scoring/value_objects.py` | MCO en PositionGroup, position_to_group, _DEFAULT_PASSES_AVG_V2 |
| `domain/scoring/services.py` | MCO en BASE_POINTS_TABLE_V2 |
| `domain/transfermarkt_ports.py` | NUEVO: DTOs + Protocols + TM_POSITION_MAP |
| `infrastructure/providers/transfermarkt_scraper.py` | NUEVO: scraper HTTP con regex |
| `infrastructure/models/player_tm_ids/__init__.py` | NUEVO (vacio + re-export) |
| `infrastructure/models/player_tm_ids/models.py` | NUEVO: modelo SQLAlchemy PlayerTmId |
| `infrastructure/repositories/player_tm_id_repository.py` | NUEVO |
| `infrastructure/repositories/enrich_position_repository.py` | NUEVO |
| `infrastructure/repositories/__init__.py` | Registrar nuevos repos |
| `application/use_cases/enrich_player_positions.py` | NUEVO: use case batch |
| `tasks/enrichment_tasks.py` | Agregar enrich_player_positions_task |
| `api/v1/admin.py` | Agregar POST /players/enrich-positions |
| `core/dependencies.py` | Wiring de nuevos componentes |
| `domain/ingestion_ports.py` | Agregar position_source a firma de upsert_player |
| `infrastructure/repositories/ingestion_repository.py` | Logica de prioridad en upsert_player |
| `application/use_cases/ingest_competition.py` | Mapear MCO en _v1_group |
| `tests/use_cases/test_enrich_player_positions.py` | NUEVO |
| `tests/providers/test_transfermarkt_scraper.py` | NUEVO |
| `http/admin_enrich_positions.http` | NUEVO |
