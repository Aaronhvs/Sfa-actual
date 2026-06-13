from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class KnockoutFixtureDTO:
    fixture_id: int
    stage: str
    home_team_id: int
    away_team_id: int


@dataclass(frozen=True)
class InferAchievementsResult:
    competition_id: int
    season: str
    skipped: bool
    achievements_upserted: int
    phases_found: list[str]


@dataclass(frozen=True)
class InferAllAchievementsResult:
    season: str
    competitions_processed: int
    competitions_skipped: int
    total_achievements_upserted: int


@runtime_checkable
class InferAchievementsRepositoryPort(Protocol):
    async def get_knockout_stage_fixtures(
        self, competition_id: int, season: str
    ) -> list[KnockoutFixtureDTO]: ...

    async def get_goals_for_fixture(
        self, fixture_id: int
    ) -> dict[int, int]: ...

    async def get_shootout_goals_for_fixture(
        self, fixture_id: int
    ) -> dict[int, int]: ...

    async def get_competition_name(self, competition_id: int) -> str: ...

    async def get_all_knockout_competition_ids(self, season: str) -> list[int]: ...
