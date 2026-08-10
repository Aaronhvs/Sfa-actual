from __future__ import annotations

import dataclasses
import datetime
from typing import Protocol, runtime_checkable

from sfa.domain.ports import (  # noqa: F401
    FixtureActionBreakdown,
    PlayerEventRepositoryProtocol,
    PlayerFixtureDTO,
    SeasonRepositoryProtocol,
    SFAScoreRepositoryProtocol,
)


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
        rules_version_id: int | None = None,
        scope: str | None = None,
    ) -> list[PlayerFixtureDTO]: ...


class GetPlayerFixturesUseCase(GetPlayerFixturesUseCaseProtocol):
    def __init__(
        self,
        event_repo: PlayerEventRepositoryProtocol,
        season_repo: SeasonRepositoryProtocol | None = None,
        score_repo: SFAScoreRepositoryProtocol | None = None,
    ) -> None:
        self._event_repo = event_repo
        self._season_repo = season_repo
        self._score_repo = score_repo

    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
        include_breakdown: bool = True,
        competition_name: str | None = None,
        rival: str | None = None,
        date: datetime.date | None = None,
        rules_version_id: int | None = None,
        scope: str | None = None,
    ) -> list[PlayerFixtureDTO]:
        if season is not None and scope is not None:
            raise ValueError("scope and season are mutually exclusive")
        resolved_scope = None
        if scope is not None:
            if self._season_repo is None or self._score_repo is None:
                raise ValueError("Scope repositories are not configured")
            resolved_scope = await self._season_repo.resolve_scope(scope)
            if resolved_scope is None:
                return []
            rules_version_id = await self._score_repo.resolve_rules_version_id_for_scope(
                resolved_scope, rules_version_id
            )
            season = None
        if season == "all":
            season = None
        fixture_kwargs = {
            "competition_name": competition_name,
            "rival": rival,
            "date": date,
        }
        if rules_version_id is not None:
            fixture_kwargs["rules_version_id"] = rules_version_id
        if resolved_scope is not None:
            fixture_kwargs["scope"] = resolved_scope
        fixtures = await self._event_repo.get_fixtures_by_player(
            player_id,
            season,
            competition_id,
            **fixture_kwargs,
        )

        if not include_breakdown or not fixtures:
            return fixtures

        fixture_ids = [f.fixture_id for f in fixtures]
        if rules_version_id is None:
            breakdown_map = await self._event_repo.get_fixture_breakdown_by_player(
                player_id, fixture_ids,
            )
        else:
            breakdown_map = await self._event_repo.get_fixture_breakdown_by_player(
                player_id, fixture_ids, season, rules_version_id,
            )

        return [
            dataclasses.replace(f, breakdown=breakdown_map.get(f.fixture_id))
            for f in fixtures
        ]
