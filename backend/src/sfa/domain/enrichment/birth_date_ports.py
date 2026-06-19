from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PlayerBirthDateRawDTO:
    external_id: int
    birth_date: date | None


@runtime_checkable
class PlayerBirthDateProviderPort(Protocol):
    async def fetch_squad_birth_dates(
        self,
        team_id: int,
        season: int,
    ) -> list[PlayerBirthDateRawDTO]: ...

    async def fetch_player_birth_date(
        self,
        player_id: int,
        season: int,
    ) -> PlayerBirthDateRawDTO | None: ...


@runtime_checkable
class BirthDateEnrichmentRepositoryPort(Protocol):
    async def get_teams_for_birth_date_refresh(
        self,
        season: str,
    ) -> list[tuple[int, int]]: ...
    # returns all (team_external_id, season_int) pairs with players in the season

    async def get_teams_missing_birth_date(
        self,
        season: str,
    ) -> list[tuple[int, int]]: ...
    # returns list of (team_external_id, season_int) pairs

    async def get_players_missing_birth_date(
        self,
        season: str,
    ) -> list[tuple[int, int]]: ...
    # returns list of (player_external_id, season_int) pairs

    async def upsert_player_birth_date(
        self,
        external_id: int,
        birth_date: date | None,
        force_update: bool = False,
    ) -> int: ...

    async def count_players_missing_birth_date(self) -> int: ...
