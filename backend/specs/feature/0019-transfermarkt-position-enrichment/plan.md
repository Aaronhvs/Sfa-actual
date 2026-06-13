# Plan: Transfermarkt Position Enrichment (Spec 0019)

## Archivos a crear

- [ ] `src/sfa/domain/transfermarkt_ports.py` — DTOs, Protocols, TM_POSITION_MAP
- [ ] `src/sfa/infrastructure/providers/transfermarkt_scraper.py` — scraper HTTP con regex
- [ ] `src/sfa/infrastructure/models/player_tm_ids/__init__.py` — init con re-export
- [ ] `src/sfa/infrastructure/models/player_tm_ids/models.py` — modelo PlayerTmId
- [ ] `src/sfa/infrastructure/repositories/player_tm_id_repository.py` — PlayerTmIdRepository
- [ ] `src/sfa/infrastructure/repositories/enrich_position_repository.py` — EnrichPositionRepository
- [ ] `src/sfa/application/use_cases/enrich_player_positions.py` — EnrichPlayerPositionsUseCase
- [ ] `tests/use_cases/test_enrich_player_positions.py` — tests con Fakes
- [ ] `tests/providers/test_transfermarkt_scraper.py` — tests de parsing con HTML mock
- [ ] `http/admin_enrich_positions.http` — casos HTTP para el endpoint admin

## Archivos a modificar

- [ ] `src/sfa/infrastructure/models/enums.py` — agregar MCO a Position
- [ ] `src/sfa/infrastructure/models/players/models.py` — agregar columna position_source
- [ ] `src/sfa/domain/scoring/value_objects.py` — MCO en PositionGroup, position_to_group, _DEFAULT_PASSES_AVG_V2
- [ ] `src/sfa/domain/scoring/services.py` — MCO en BASE_POINTS_TABLE_V2
- [ ] `src/sfa/domain/ingestion_ports.py` — agregar position_source a firma de upsert_player
- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py` — logica de prioridad en upsert_player
- [ ] `src/sfa/infrastructure/repositories/__init__.py` — registrar PlayerTmIdRepository, EnrichPositionRepository
- [ ] `src/sfa/application/use_cases/ingest_competition.py` — mapear MCO en _v1_group
- [ ] `src/sfa/tasks/enrichment_tasks.py` — agregar enrich_player_positions_task
- [ ] `src/sfa/api/v1/admin.py` — agregar POST /players/enrich-positions
- [ ] `src/sfa/core/dependencies.py` — wiring de nuevos componentes

---

## Checklist de implementacion

### PASO 1 — Migracion SQL (ejecutar manualmente en PostgreSQL antes de levantar la app)

```sql
-- 1a. Columna position_source en players
ALTER TABLE players
  ADD COLUMN IF NOT EXISTS position_source VARCHAR(20) NOT NULL DEFAULT 'apifootball';

COMMENT ON COLUMN players.position_source IS
  'Origin of the position value: transfermarkt | apifootball | heuristic | manual';

-- 1b. Tabla player_tm_ids
CREATE TABLE IF NOT EXISTS player_tm_ids (
    id          SERIAL PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    tm_id       INTEGER NOT NULL,
    verified    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_id),
    UNIQUE (tm_id)
);

CREATE INDEX IF NOT EXISTS ix_player_tm_ids_player_id ON player_tm_ids(player_id);
CREATE INDEX IF NOT EXISTS ix_player_tm_ids_tm_id ON player_tm_ids(tm_id);
```

---

### PASO 2 — Enum Position: agregar MCO

Archivo: `src/sfa/infrastructure/models/enums.py`

Agregar `MCO = "MCO"` entre MC y EXT:

```python
class Position(str, Enum):
    GK  = "GK"
    DC  = "DC"
    LAT = "LAT"
    MC  = "MC"
    MCO = "MCO"   # Attacking Midfield / Mediapunta
    EXT = "EXT"
    DEL = "DEL"
```

---

### PASO 3 — PositionGroup y mappings en value_objects.py

Archivo: `src/sfa/domain/scoring/value_objects.py`

**3a.** Agregar `MCO = "MCO"` en la clase `PositionGroup`, entre MF y LAT:

```python
class PositionGroup(str, Enum):
    DEL = "DEL"
    EXT = "EXT"
    MF  = "MF"
    MCO = "MCO"   # Attacking Midfield / Mediapunta
    LAT = "LAT"
    DC  = "DC"
    FW  = "FW"    # deprecated
    DF  = "DF"    # deprecated
```

**3b.** Actualizar `position_to_group` para incluir MCO:

```python
mapping: dict[Position, PositionGroup] = {
    Position.DEL: PositionGroup.DEL,
    Position.EXT: PositionGroup.EXT,
    Position.MC:  PositionGroup.MF,
    Position.MCO: PositionGroup.MCO,   # nuevo
    Position.LAT: PositionGroup.LAT,
    Position.DC:  PositionGroup.DC,
}
```

**3c.** Actualizar `_DEFAULT_PASSES_AVG_V2` para incluir MCO:

```python
_DEFAULT_PASSES_AVG_V2: dict[str, int] = {
    "DEL": 20, "EXT": 28, "MF": 50, "MCO": 35, "LAT": 38, "DC": 32,
}
```

El metodo `default_v2()` tomara MCO automaticamente al hacer `{PositionGroup(k): v for k, v in _DEFAULT_PASSES_AVG_V2.items()}`.

---

### PASO 4 — BASE_POINTS_TABLE_V2: nueva fila MCO

Archivo: `src/sfa/domain/scoring/services.py`

Agregar la entrada de MCO en `BASE_POINTS_TABLE_V2` (despues de EXT, antes de MF, o al final — el orden del dict no afecta la logica):

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
},
```

---

### PASO 5 — Actualizar _v1_group en ingest_competition.py

Archivo: `src/sfa/application/use_cases/ingest_competition.py`

En la funcion `_v1_group`, agregar el mapeo de MCO a MF para el fallback de v1:

```python
_V2_TO_V1_GROUP.update({
    PositionGroup.DEL: PositionGroup.FW,
    PositionGroup.EXT: PositionGroup.FW,
    PositionGroup.MF:  PositionGroup.MF,
    PositionGroup.MCO: PositionGroup.MF,   # nuevo: MCO fallback a MF en v1
    PositionGroup.LAT: PositionGroup.DF,
    PositionGroup.DC:  PositionGroup.DF,
})
```

---

### PASO 6 — Agregar position_source al modelo Player

Archivo: `src/sfa/infrastructure/models/players/models.py`

Agregar al final de la clase `Player` (despues de `understat_id`):

```python
position_source: Mapped[str] = mapped_column(
    String(20), nullable=False, server_default="apifootball"
)
```

Tambien agregar comentario de migracion al bloque existente:

```python
# Migration:
# ALTER TABLE players ADD COLUMN fbref_id VARCHAR(150) UNIQUE;
# ALTER TABLE players ADD COLUMN understat_id INTEGER UNIQUE;
# ALTER TABLE players ADD COLUMN IF NOT EXISTS position_source VARCHAR(20) NOT NULL DEFAULT 'apifootball';
```

---

### PASO 7 — Modelo SQLAlchemy PlayerTmId

**7a.** Crear directorio `src/sfa/infrastructure/models/player_tm_ids/`.

**7b.** Crear `src/sfa/infrastructure/models/player_tm_ids/__init__.py`:

```python
from .models import PlayerTmId  # noqa: F401

__all__ = ["PlayerTmId"]
```

**7c.** Crear `src/sfa/infrastructure/models/player_tm_ids/models.py`:

```python
import datetime

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class PlayerTmId(Base):
    __tablename__ = "player_tm_ids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    tm_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default="NOW()",
    )

    # Migration: see PASO 1 SQL above
```

---

### PASO 8 — Domain ports: transfermarkt_ports.py

Crear `src/sfa/domain/transfermarkt_ports.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.infrastructure.models.enums import Position


@dataclass(frozen=True)
class TmPlayerData:
    tm_id: int
    position_raw: str       # texto crudo de TM, ej. "Central Midfield"
    position_mapped: Position   # enum SFA mapeado


@dataclass(frozen=True)
class TmSearchResult:
    tm_id: int
    name: str
    team_name: str
    slug: str               # slug de URL de TM, ej. "vitinha"


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


# ---------------------------------------------------------------------------
# Mapping Transfermarkt position strings -> SFA Position enum
# ---------------------------------------------------------------------------

TM_POSITION_MAP: dict[str, Position] = {
    "Goalkeeper":         Position.GK,
    "Centre-Back":        Position.DC,
    "Right-Back":         Position.LAT,
    "Left-Back":          Position.LAT,
    "Right Midfield":     Position.LAT,   # carrilero derecho
    "Left Midfield":      Position.LAT,   # carrilero izquierdo
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


# ---------------------------------------------------------------------------
# Ports (Protocols)
# ---------------------------------------------------------------------------

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

---

### PASO 9 — TransfermarktScraper (provider)

Crear `src/sfa/infrastructure/providers/transfermarkt_scraper.py`.

Reglas estrictas:
- Unicos imports externos: `re`, `httpx`, `asyncio`, `urllib.parse`, `logging`
- Sin BeautifulSoup
- `_POSITION_PATTERN` es una constante de modulo (los tests la importan directamente)
- `_get_html` retorna `str | None` — NUNCA lanza excepcion al caller
- El sleep de rate-limit NO va aqui — va en el use case

```python
from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse

import httpx

from sfa.domain.transfermarkt_ports import TM_POSITION_MAP, TmPlayerData, TmSearchResult

logger = logging.getLogger(__name__)

_TM_BASE = "https://www.transfermarkt.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Patron para extraer la posicion del perfil de TM.
# Busca el span "data-header__content" inmediatamente despues de "Position:"
_POSITION_PATTERN = re.compile(
    r'Position:</span>\s*<span[^>]*class="[^"]*data-header__content[^"]*"[^>]*>\s*([^<]+?)\s*</span>',
    re.IGNORECASE | re.DOTALL,
)

# Patron para extraer tm_id de un href de perfil: /profil/spieler/388282
_TM_ID_PATTERN = re.compile(r'/profil/spieler/(\d+)')

# Patron para extraer slug y tm_id de un href de perfil completo
_PROFILE_HREF_PATTERN = re.compile(r'/([^/]+)/profil/spieler/(\d+)')


class TransfermarktScraper:
    """HTTP scraper para Transfermarkt. Sin BeautifulSoup — parseo con regex."""

    async def _get_html(self, url: str) -> str | None:
        """Retorna el HTML de la URL, o None en 404/timeout/error. No lanza."""
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS,
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    logger.warning("[TransfermarktScraper] 404 for %s", url)
                    return None
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as exc:
            logger.warning("[TransfermarktScraper] HTTP error for %s: %s", url, exc)
            return None
        except httpx.RequestError as exc:
            logger.warning("[TransfermarktScraper] Request error for %s: %s", url, exc)
            return None

    async def fetch_player_position(self, tm_id: int, slug: str) -> TmPlayerData | None:
        """Obtiene la posicion de un jugador por tm_id y slug de URL."""
        url = f"{_TM_BASE}/{slug}/profil/spieler/{tm_id}"
        html = await self._get_html(url)
        if not html:
            return None

        match = _POSITION_PATTERN.search(html)
        if not match:
            logger.warning(
                "[TransfermarktScraper] Position not found in profile tm_id=%s", tm_id
            )
            return None

        position_raw = match.group(1).strip()
        position_mapped = TM_POSITION_MAP.get(position_raw)
        if position_mapped is None:
            logger.warning(
                "[TransfermarktScraper] Unknown TM position %r for tm_id=%s", position_raw, tm_id
            )
            return None

        return TmPlayerData(
            tm_id=tm_id,
            position_raw=position_raw,
            position_mapped=position_mapped,
        )

    async def search_player(self, name: str, team_name: str) -> TmSearchResult | None:
        """Busca un jugador por nombre+equipo en el endpoint schnellsuche."""
        encoded = urllib.parse.quote(name)
        url = f"{_TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={encoded}&x=0&y=0"
        html = await self._get_html(url)
        if not html:
            return None

        # Buscar todos los hrefs de perfil en el HTML
        for m in _PROFILE_HREF_PATTERN.finditer(html):
            slug = m.group(1)
            tm_id = int(m.group(2))

            # Extraer contexto alrededor del match para verificar el equipo
            start = max(0, m.start() - 300)
            end = min(len(html), m.end() + 300)
            context = html[start:end].lower()

            if team_name.lower() in context or any(
                part in context for part in team_name.lower().split()
            ):
                logger.info(
                    "[TransfermarktScraper] Found tm_id=%s slug=%s for %s (%s)",
                    tm_id, slug, name, team_name,
                )
                return TmSearchResult(
                    tm_id=tm_id,
                    name=name,
                    team_name=team_name,
                    slug=slug,
                )

        logger.info(
            "[TransfermarktScraper] No TM match for %s (%s)", name, team_name
        )
        return None
```

---

### PASO 10 — PlayerTmIdRepository

Crear `src/sfa/infrastructure/repositories/player_tm_id_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.transfermarkt_ports import PlayerTmIdRow, PlayerTmIdRepositoryPort
from sfa.infrastructure.models.player_tm_ids.models import PlayerTmId


class PlayerTmIdRepository(PlayerTmIdRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_tm_id(self, player_id: int) -> PlayerTmIdRow | None:
        stmt = select(PlayerTmId).where(PlayerTmId.player_id == player_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return PlayerTmIdRow(player_id=row.player_id, tm_id=row.tm_id, verified=row.verified)

    async def upsert_tm_id(self, player_id: int, tm_id: int, verified: bool) -> None:
        stmt = (
            pg_insert(PlayerTmId)
            .values(player_id=player_id, tm_id=tm_id, verified=verified)
            .on_conflict_do_update(
                index_elements=["player_id"],
                set_={"tm_id": tm_id, "verified": verified},
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
```

---

### PASO 11 — EnrichPositionRepository

Crear `src/sfa/infrastructure/repositories/enrich_position_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.transfermarkt_ports import EnrichPositionRepositoryPort, PlayerForEnrichDTO
from sfa.infrastructure.models.enums import Position
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.teams.models import Team


class EnrichPositionRepository(EnrichPositionRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_players_without_tm_source(self, limit: int) -> list[PlayerForEnrichDTO]:
        stmt = (
            select(
                Player.id,
                Player.name,
                Team.name.label("team_name"),
                Player.position_source,
            )
            .join(Team, Player.team_id == Team.id)
            .where(Player.position_source != "transfermarkt")
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            PlayerForEnrichDTO(
                id=row["id"],
                name=row["name"],
                team_name=row["team_name"],
                position_source=row["position_source"],
            )
            for row in rows
        ]

    async def update_player_position(
        self, player_id: int, position: Position, source: str,
    ) -> None:
        stmt = (
            update(Player)
            .where(Player.id == player_id)
            .values(position=position, position_source=source)
        )
        await self._session.execute(stmt)
        await self._session.flush()
```

---

### PASO 12 — Actualizar upsert_player: logica de prioridad de fuente

**12a.** Archivo: `src/sfa/domain/ingestion_ports.py`

Actualizar la firma del metodo `upsert_player` en `IngestionRepositoryPort`:

```python
async def upsert_player(
    self, external_id: int, name: str, team_id: int, position: Position,
    photo_url: str | None = None,
    update_position: bool = True,
    position_source: str = "apifootball",
) -> int: ...
```

**12b.** Archivo: `src/sfa/infrastructure/repositories/ingestion_repository.py`

Modificar el metodo `upsert_player`. El invariante es: si el registro ya existe y tiene
`position_source = 'transfermarkt'`, NO actualizar `position` ni `position_source`.

```python
async def upsert_player(
    self, external_id: int, name: str, team_id: int, position: Position,
    photo_url: str | None = None,
    update_position: bool = True,
    position_source: str = "apifootball",
) -> int:
    insert_stmt = pg_insert(Player).values(
        external_id=external_id, name=name, team_id=team_id,
        position=position, photo_url=photo_url, position_source=position_source,
    )
    set_dict = {
        "name": insert_stmt.excluded.name,
        "team_id": insert_stmt.excluded.team_id,
        "photo_url": func.coalesce(insert_stmt.excluded.photo_url, Player.photo_url),
    }
    if update_position:
        # Solo actualizar position/position_source si la fuente actual NO es 'transfermarkt'
        set_dict["position"] = func.case(
            (Player.position_source == "transfermarkt", Player.position),
            else_=insert_stmt.excluded.position,
        )
        set_dict["position_source"] = func.case(
            (Player.position_source == "transfermarkt", Player.position_source),
            else_=insert_stmt.excluded.position_source,
        )

    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["external_id"],
        set_=set_dict,
    ).returning(Player.id)
    result = await self._session.execute(stmt)
    await self._session.flush()
    return result.scalar_one()
```

---

### PASO 13 — EnrichPlayerPositionsUseCase

Crear `src/sfa/application/use_cases/enrich_player_positions.py`:

```python
from __future__ import annotations

import asyncio
import logging

from sfa.domain.transfermarkt_ports import (
    EnrichPositionRepositoryPort,
    EnrichPositionsResult,
    PlayerTmIdRepositoryPort,
    TransfermarktProviderPort,
)

logger = logging.getLogger(__name__)


class EnrichPlayerPositionsUseCase:
    def __init__(
        self,
        provider: TransfermarktProviderPort,
        tm_id_repo: PlayerTmIdRepositoryPort,
        enrich_repo: EnrichPositionRepositoryPort,
    ) -> None:
        self._provider = provider
        self._tm_id_repo = tm_id_repo
        self._enrich_repo = enrich_repo

    async def execute(self, batch_size: int = 500) -> EnrichPositionsResult:
        players = await self._enrich_repo.get_players_without_tm_source(batch_size)

        matched = 0
        position_updated = 0
        unmatched = 0
        failed = 0
        skipped_already_tm = 0

        for player in players:
            if player.position_source == "transfermarkt":
                skipped_already_tm += 1
                continue
            try:
                tm_row = await self._tm_id_repo.get_tm_id(player.id)
                if tm_row:
                    # Cache hit: ya tenemos el tm_id, construir slug basico
                    tm_id = tm_row.tm_id
                    slug = player.name.lower().replace(" ", "-")
                else:
                    # Cache miss: buscar en TM por nombre+equipo
                    search = await self._provider.search_player(player.name, player.team_name)
                    await asyncio.sleep(1.0)   # rate limit
                    if not search:
                        unmatched += 1
                        logger.info(
                            "[EnrichPlayerPositionsUseCase] No TM match: %s (%s)",
                            player.name, player.team_name,
                        )
                        continue
                    tm_id = search.tm_id
                    slug = search.slug
                    await self._tm_id_repo.upsert_tm_id(player.id, tm_id, verified=False)

                tm_data = await self._provider.fetch_player_position(tm_id, slug)
                await asyncio.sleep(1.0)   # rate limit
                if not tm_data:
                    unmatched += 1
                    continue

                matched += 1
                await self._enrich_repo.update_player_position(
                    player.id, tm_data.position_mapped, "transfermarkt"
                )
                position_updated += 1
                logger.info(
                    "[EnrichPlayerPositionsUseCase] Updated player_id=%s: %s -> %s",
                    player.id, player.name, tm_data.position_raw,
                )

            except Exception as exc:
                failed += 1
                logger.error(
                    "[EnrichPlayerPositionsUseCase] Failed player_id=%s (%s): %s",
                    player.id, player.name, exc,
                )

        logger.info(
            "[EnrichPlayerPositionsUseCase] Done. total=%s matched=%s updated=%s "
            "unmatched=%s failed=%s skipped=%s",
            len(players), matched, position_updated, unmatched, failed, skipped_already_tm,
        )
        return EnrichPositionsResult(
            total_processed=len(players),
            matched=matched,
            position_updated=position_updated,
            unmatched=unmatched,
            failed=failed,
            skipped_already_tm=skipped_already_tm,
        )
```

---

### PASO 14 — Celery task

Archivo: `src/sfa/tasks/enrichment_tasks.py`

Agregar al final del archivo, siguiendo el patron existente de late imports:

```python
@celery_app.task(name="enrich_player_positions_task", bind=True, max_retries=0)
def enrich_player_positions_task(self, batch_size: int = 500) -> dict:
    """Enrich player positions from Transfermarkt. Rate-limited to 1 req/sec."""
    import asyncio

    from sfa.application.use_cases.enrich_player_positions import EnrichPlayerPositionsUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.transfermarkt_scraper import TransfermarktScraper
    from sfa.infrastructure.repositories.enrich_position_repository import EnrichPositionRepository
    from sfa.infrastructure.repositories.player_tm_id_repository import PlayerTmIdRepository

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            use_case = EnrichPlayerPositionsUseCase(
                provider=TransfermarktScraper(),
                tm_id_repo=PlayerTmIdRepository(session),
                enrich_repo=EnrichPositionRepository(session),
            )
            result = await use_case.execute(batch_size=batch_size)
            await session.commit()
            return {
                "total_processed": result.total_processed,
                "matched": result.matched,
                "position_updated": result.position_updated,
                "unmatched": result.unmatched,
                "failed": result.failed,
                "skipped_already_tm": result.skipped_already_tm,
            }

    return asyncio.get_event_loop().run_until_complete(_run())
```

---

### PASO 15 — Admin endpoint

Archivo: `src/sfa/api/v1/admin.py`

Agregar import de la nueva task:

```python
from sfa.tasks.enrichment_tasks import (
    backfill_fixture_stats_task,
    enrich_all_task,
    enrich_player_positions_task,   # nuevo
    recalculate_task,
)
```

Agregar endpoint al router (despues del endpoint `/players/fix-positions` existente):

```python
@router.post("/players/enrich-positions")
async def trigger_enrich_player_positions(
    batch_size: int = Query(default=500, ge=1, le=5000),
):
    """Enrich player positions from Transfermarkt (Celery background task).

    Rate-limited to 1 req/sec -- expect 1+ hours for batches > 3600.
    Run /players/fix-positions (spec 0018) first to clean up base positions.
    """
    task = enrich_player_positions_task.delay(batch_size)
    return {"task_id": task.id, "batch_size": batch_size}
```

---

### PASO 16 — HTTP file

Crear `http/admin_enrich_positions.http`:

```http
### Enrich player positions from Transfermarkt (batch default=500)
POST http://localhost:8000/api/v1/admin/players/enrich-positions?batch_size=500

### Enrich small batch for smoke-testing (10 players)
POST http://localhost:8000/api/v1/admin/players/enrich-positions?batch_size=10

### Fix positions first (spec 0018 prerequisite)
POST http://localhost:8000/api/v1/admin/players/fix-positions

### Full batch (all players without TM source, max allowed)
POST http://localhost:8000/api/v1/admin/players/enrich-positions?batch_size=5000
```

---

### PASO 17 — Dependencies wiring

Archivo: `src/sfa/core/dependencies.py`

Agregar los imports y factories al final del bloque de repositorios y use cases:

```python
# ─── Nuevos repos para enrichment de posiciones TM ──────────────────
from sfa.infrastructure.repositories.enrich_position_repository import EnrichPositionRepository
from sfa.infrastructure.repositories.player_tm_id_repository import PlayerTmIdRepository


async def get_player_tm_id_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerTmIdRepository:
    return PlayerTmIdRepository(db)


async def get_enrich_position_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnrichPositionRepository:
    return EnrichPositionRepository(db)


# ─── Use case factory ────────────────────────────────────────────────
from sfa.application.use_cases.enrich_player_positions import EnrichPlayerPositionsUseCase


async def get_enrich_player_positions_use_case(
    tm_id_repo: Annotated[PlayerTmIdRepository, Depends(get_player_tm_id_repository)],
    enrich_repo: Annotated[EnrichPositionRepository, Depends(get_enrich_position_repository)],
) -> EnrichPlayerPositionsUseCase:
    from sfa.infrastructure.providers.transfermarkt_scraper import TransfermarktScraper

    return EnrichPlayerPositionsUseCase(
        provider=TransfermarktScraper(),
        tm_id_repo=tm_id_repo,
        enrich_repo=enrich_repo,
    )
```

---

### PASO 18 — Registrar nuevos repositories en __init__.py

Archivo: `src/sfa/infrastructure/repositories/__init__.py`

Agregar los dos nuevos repos al bloque de exports existente:

```python
from .enrich_position_repository import EnrichPositionRepository
from .player_tm_id_repository import PlayerTmIdRepository
```

---

### PASO 19 — Tests

**Test 1:** Crear `tests/providers/test_transfermarkt_scraper.py`

```python
import re

import pytest

from sfa.domain.transfermarkt_ports import TM_POSITION_MAP
from sfa.infrastructure.models.enums import Position
from sfa.infrastructure.providers.transfermarkt_scraper import _POSITION_PATTERN

MOCK_PROFILE_CENTRAL_MF = """
<html><body>
  <div class="data-header__label">
    Position:</span>
    <span class="data-header__content">Central Midfield</span>
  </div>
</body></html>
"""

MOCK_PROFILE_ATTACKING_MF = """
<html><body>
  <div class="data-header__label">
    Position:</span>
    <span class="data-header__content">Attacking Midfield</span>
  </div>
</body></html>
"""

MOCK_PROFILE_RIGHT_BACK = """
<html><body>
  <div class="data-header__label">
    Position:</span>
    <span class="data-header__content">Right-Back</span>
  </div>
</body></html>
"""


class TestTransfermarktPositionPattern:
    def test_parse_central_midfield(self):
        m = _POSITION_PATTERN.search(MOCK_PROFILE_CENTRAL_MF)
        assert m is not None
        assert m.group(1).strip() == "Central Midfield"

    def test_parse_attacking_midfield(self):
        m = _POSITION_PATTERN.search(MOCK_PROFILE_ATTACKING_MF)
        assert m is not None
        assert m.group(1).strip() == "Attacking Midfield"

    def test_parse_right_back(self):
        m = _POSITION_PATTERN.search(MOCK_PROFILE_RIGHT_BACK)
        assert m is not None
        assert m.group(1).strip() == "Right-Back"

    def test_no_match_on_empty_html(self):
        assert _POSITION_PATTERN.search("<html></html>") is None


class TestTmPositionMap:
    def test_attacking_midfield_maps_to_mco(self):
        assert TM_POSITION_MAP["Attacking Midfield"] == Position.MCO

    def test_central_midfield_maps_to_mc(self):
        assert TM_POSITION_MAP["Central Midfield"] == Position.MC

    def test_right_back_maps_to_lat(self):
        assert TM_POSITION_MAP["Right-Back"] == Position.LAT

    def test_centre_forward_maps_to_del(self):
        assert TM_POSITION_MAP["Centre-Forward"] == Position.DEL

    def test_mco_in_position_enum(self):
        assert Position.MCO == "MCO"

    def test_all_map_values_are_valid_position_enum(self):
        for key, val in TM_POSITION_MAP.items():
            assert isinstance(val, Position), f"Invalid Position for key {key!r}: {val!r}"
```

**Test 2:** Crear `tests/use_cases/test_enrich_player_positions.py`

```python
from __future__ import annotations

import pytest

from sfa.application.use_cases.enrich_player_positions import EnrichPlayerPositionsUseCase
from sfa.domain.transfermarkt_ports import (
    EnrichPositionRepositoryPort,
    PlayerForEnrichDTO,
    PlayerTmIdRepositoryPort,
    PlayerTmIdRow,
    TmPlayerData,
    TmSearchResult,
    TransfermarktProviderPort,
)
from sfa.infrastructure.models.enums import Position


# ---------------------------------------------------------------------------
# Fakes — implementan el Protocol completo, nunca MagicMock
# ---------------------------------------------------------------------------

class FakeTransfermarktProvider(TransfermarktProviderPort):
    def __init__(
        self,
        search_result: TmSearchResult | None = None,
        position_data: TmPlayerData | None = None,
    ) -> None:
        self._search = search_result
        self._position = position_data

    async def search_player(self, name: str, team_name: str) -> TmSearchResult | None:
        return self._search

    async def fetch_player_position(self, tm_id: int, slug: str) -> TmPlayerData | None:
        return self._position


class FakePlayerTmIdRepo(PlayerTmIdRepositoryPort):
    def __init__(self) -> None:
        self.stored: dict[int, PlayerTmIdRow] = {}

    async def get_tm_id(self, player_id: int) -> PlayerTmIdRow | None:
        return self.stored.get(player_id)

    async def upsert_tm_id(self, player_id: int, tm_id: int, verified: bool) -> None:
        self.stored[player_id] = PlayerTmIdRow(
            player_id=player_id, tm_id=tm_id, verified=verified
        )


class FakeEnrichPositionRepo(EnrichPositionRepositoryPort):
    def __init__(self, players: list[PlayerForEnrichDTO]) -> None:
        self._players = players
        self.updates: list[tuple] = []

    async def get_players_without_tm_source(self, limit: int) -> list[PlayerForEnrichDTO]:
        return self._players[:limit]

    async def update_player_position(
        self, player_id: int, position: Position, source: str,
    ) -> None:
        self.updates.append((player_id, position, source))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEnrichPlayerPositionsUseCase:

    @pytest.mark.anyio
    async def test_successful_enrichment_updates_position(self):
        player = PlayerForEnrichDTO(
            id=1, name="Vitinha", team_name="Paris Saint-Germain", position_source="apifootball"
        )
        search = TmSearchResult(tm_id=388282, name="Vitinha", team_name="Paris Saint-Germain", slug="vitinha")
        pos_data = TmPlayerData(tm_id=388282, position_raw="Central Midfield", position_mapped=Position.MC)

        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(search_result=search, position_data=pos_data),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=FakeEnrichPositionRepo([player]),
        )
        result = await use_case.execute(batch_size=10)

        assert result.matched == 1
        assert result.position_updated == 1
        assert result.unmatched == 0
        assert result.failed == 0
        assert result.skipped_already_tm == 0

    @pytest.mark.anyio
    async def test_updates_with_mco_for_attacking_midfield(self):
        player = PlayerForEnrichDTO(
            id=2, name="Bruno Fernandes", team_name="Manchester United", position_source="apifootball"
        )
        search = TmSearchResult(tm_id=240306, name="Bruno Fernandes", team_name="Manchester United", slug="bruno-fernandes")
        pos_data = TmPlayerData(tm_id=240306, position_raw="Attacking Midfield", position_mapped=Position.MCO)

        enrich_repo = FakeEnrichPositionRepo([player])
        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(search_result=search, position_data=pos_data),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=enrich_repo,
        )
        result = await use_case.execute(batch_size=10)

        assert result.position_updated == 1
        assert enrich_repo.updates[0] == (2, Position.MCO, "transfermarkt")

    @pytest.mark.anyio
    async def test_unmatched_player_increments_counter(self):
        player = PlayerForEnrichDTO(
            id=3, name="Unknown Player", team_name="Unknown FC", position_source="apifootball"
        )
        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(search_result=None, position_data=None),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=FakeEnrichPositionRepo([player]),
        )
        result = await use_case.execute(batch_size=10)

        assert result.unmatched == 1
        assert result.matched == 0
        assert result.position_updated == 0

    @pytest.mark.anyio
    async def test_cached_tm_id_skips_search(self):
        """Si ya tenemos tm_id en cache, no se llama a search_player."""
        player = PlayerForEnrichDTO(
            id=4, name="Virgil van Dijk", team_name="Liverpool", position_source="apifootball"
        )
        pos_data = TmPlayerData(tm_id=139208, position_raw="Centre-Back", position_mapped=Position.DC)

        # Provider con search que falla (search_result=None), pero position_data OK
        provider = FakeTransfermarktProvider(search_result=None, position_data=pos_data)
        tm_id_repo = FakePlayerTmIdRepo()
        await tm_id_repo.upsert_tm_id(4, 139208, verified=True)  # pre-cargar cache

        enrich_repo = FakeEnrichPositionRepo([player])
        use_case = EnrichPlayerPositionsUseCase(provider, tm_id_repo, enrich_repo)
        result = await use_case.execute(batch_size=10)

        assert result.matched == 1
        assert result.position_updated == 1
        assert enrich_repo.updates[0] == (4, Position.DC, "transfermarkt")

    @pytest.mark.anyio
    async def test_skips_players_already_from_transfermarkt(self):
        player = PlayerForEnrichDTO(
            id=5, name="Already Enriched", team_name="FC Barcelona", position_source="transfermarkt"
        )
        enrich_repo = FakeEnrichPositionRepo([player])
        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=enrich_repo,
        )
        result = await use_case.execute(batch_size=10)

        assert result.skipped_already_tm == 1
        assert result.matched == 0
        assert len(enrich_repo.updates) == 0

    @pytest.mark.anyio
    async def test_failed_player_increments_counter_and_continues(self):
        """Una excepcion en un jugador no detiene el batch."""
        class BrokenProvider(TransfermarktProviderPort):
            async def search_player(self, name, team_name):
                raise RuntimeError("Network error")
            async def fetch_player_position(self, tm_id, slug):
                return None

        player = PlayerForEnrichDTO(id=6, name="Error Player", team_name="FC Error", position_source="apifootball")
        use_case = EnrichPlayerPositionsUseCase(
            provider=BrokenProvider(),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=FakeEnrichPositionRepo([player]),
        )
        result = await use_case.execute(batch_size=10)

        assert result.failed == 1
        assert result.matched == 0

    @pytest.mark.anyio
    async def test_result_total_reflects_batch(self):
        players = [
            PlayerForEnrichDTO(id=i, name=f"Player {i}", team_name="FC Test", position_source="apifootball")
            for i in range(5)
        ]
        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(search_result=None),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=FakeEnrichPositionRepo(players),
        )
        result = await use_case.execute(batch_size=3)

        assert result.total_processed == 3  # batch_size limita
```

---

### PASO 20 — Verificaciones finales

- [ ] Ejecutar la migracion SQL del PASO 1 en PostgreSQL
- [ ] Correr `pytest tests/` — confirmar que tests nuevos pasan y no hay regresiones
- [ ] Verificar `position_to_group(Position.MCO)` retorna `PositionGroup.MCO`
- [ ] Verificar `ScoringConfig.default_v2().base_points` incluye `PositionGroup.MCO`
- [ ] Verificar `ScoringConfig.default_v2().passes_avg_by_position` incluye `PositionGroup.MCO` con valor 35
- [ ] Verificar que `upsert_player` con `position_source='transfermarkt'` en DB NO actualiza position (test manual o test de integracion)
- [ ] Correr `POST /api/v1/admin/players/fix-positions` (prerequisito spec 0018)
- [ ] Correr `POST /api/v1/admin/players/enrich-positions?batch_size=10` (smoke test)
- [ ] Verificar logs de Celery: `[EnrichPlayerPositionsUseCase] Done. total=10 matched=X`
- [ ] Correr `flake8 src/ tests/` sin errores
- [ ] Correr `isort --check-only src/ tests/` sin errores

---

## Agent Routing Brief

**DDD Designer needed:** no

Los nuevos DTOs y Protocols de dominio (`TmPlayerData`, `TmSearchResult`, `PlayerTmIdRow`,
`PlayerForEnrichDTO`, `EnrichPositionsResult`, `TransfermarktProviderPort`,
`PlayerTmIdRepositoryPort`, `EnrichPositionRepositoryPort`) son estructuralmente simples
(frozen dataclasses + Protocols sin invariantes complejos) y estan completamente especificados
en este plan. No hay entidades de dominio con logica de negocio que requieran modelado DDD
adicional. El Architecture-Engineer los ha definido directamente en `decisions.md`.

## Verificacion end-to-end

1. `pytest tests/use_cases/test_enrich_player_positions.py -v` — todos los tests pasan
2. `pytest tests/providers/test_transfermarkt_scraper.py -v` — todos los tests pasan
3. `python -c "from sfa.domain.scoring.value_objects import position_to_group, PositionGroup; from sfa.infrastructure.models.enums import Position; assert position_to_group(Position.MCO) == PositionGroup.MCO; print('OK')"` — imprime OK
4. `python -c "from sfa.domain.scoring.value_objects import ScoringConfig, PositionGroup; cfg = ScoringConfig.default_v2(); assert PositionGroup.MCO in cfg.base_points; assert cfg.passes_avg_by_position[PositionGroup.MCO] == 35; print('OK')"` — imprime OK
5. `POST /api/v1/admin/players/enrich-positions?batch_size=5` — responde `{"task_id": "...", "batch_size": 5}` y el worker de Celery procesa sin excepcion
