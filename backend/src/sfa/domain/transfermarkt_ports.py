from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.infrastructure.models.enums import Position


@dataclass(frozen=True)
class TmPlayerData:
    tm_id: int
    position_raw: str
    position_mapped: Position


@dataclass(frozen=True)
class TmSearchResult:
    tm_id: int
    name: str
    team_name: str
    slug: str


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


TM_POSITION_MAP: dict[str, Position] = {
    "Goalkeeper": Position.GK,
    "Centre-Back": Position.DC,
    "Right-Back": Position.LAT,
    "Left-Back": Position.LAT,
    "Right Midfield": Position.LAT,
    "Left Midfield": Position.LAT,
    "Defensive Midfield": Position.MC,
    "Central Midfield": Position.MC,
    "Attacking Midfield": Position.MCO,
    "Right Winger": Position.EXT,
    "Left Winger": Position.EXT,
    "Second Striker": Position.EXT,
    "Centre-Forward": Position.DEL,
}


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
    async def get_players_without_tm_source(
        self,
        limit: int,
        season: str | None = None,
    ) -> list[PlayerForEnrichDTO]: ...

    async def update_player_position(
        self, player_id: int, position: Position, source: str,
    ) -> None: ...
