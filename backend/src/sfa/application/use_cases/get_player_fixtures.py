from __future__ import annotations

import dataclasses
import datetime
from typing import Protocol, runtime_checkable

from sfa.domain.ports import FixtureActionBreakdown, PlayerEventRepositoryProtocol, PlayerFixtureDTO  # noqa: F401


@runtime_checkable
class GetPlayerFixturesUseCaseProtocol(Protocol):
    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
        include_breakdown: bool = True,
        competition_name: str | None = None,
        rival: str | None = None,
        date: datetime.date | None = None,
    ) -> list[PlayerFixtureDTO]: ...


class GetPlayerFixturesUseCase(GetPlayerFixturesUseCaseProtocol):
    def __init__(self, event_repo: PlayerEventRepositoryProtocol) -> None:
        self._event_repo = event_repo

    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
        include_breakdown: bool = True,
        competition_name: str | None = None,
        rival: str | None = None,
        date: datetime.date | None = None,
    ) -> list[PlayerFixtureDTO]:
        if season == "all":
            season = None
        fixtures = await self._event_repo.get_fixtures_by_player(
            player_id,
            season,
            competition_id,
            competition_name=competition_name,
            rival=rival,
            date=date,
        )

        if not include_breakdown or not fixtures:
            return fixtures

        fixture_ids = [f.fixture_id for f in fixtures]
        breakdown_map = await self._event_repo.get_fixture_breakdown_by_player(player_id, fixture_ids)

        return [
            dataclasses.replace(f, breakdown=breakdown_map.get(f.fixture_id))
            for f in fixtures
        ]
