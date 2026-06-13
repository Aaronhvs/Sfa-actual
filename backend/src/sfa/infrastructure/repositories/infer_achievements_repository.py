from __future__ import annotations

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.infer_achievements_ports import (
    InferAchievementsRepositoryPort,
    KnockoutFixtureDTO,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixtures.models import Fixture


class InferAchievementsRepository(InferAchievementsRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_knockout_stage_fixtures(
        self, competition_id: int, season: str
    ) -> list[KnockoutFixtureDTO]:
        stmt = (
            select(
                Fixture.id,
                Fixture.stage,
                Fixture.home_team_id,
                Fixture.away_team_id,
            )
            .where(
                Fixture.competition_id == competition_id,
                Fixture.season == season,
                Fixture.stage != "regular",
            )
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            KnockoutFixtureDTO(
                fixture_id=row["id"],
                stage=row["stage"],
                home_team_id=row["home_team_id"],
                away_team_id=row["away_team_id"],
            )
            for row in rows
        ]

    async def get_goals_for_fixture(self, fixture_id: int) -> dict[int, int]:
        stmt = (
            select(PlayerEvent.team_id)
            .where(
                PlayerEvent.fixture_id == fixture_id,
                PlayerEvent.event_type.in_([EventType.GOAL, EventType.GOAL_PENALTY]),
            )
        )
        rows = (await self._session.execute(stmt)).all()
        result: dict[int, int] = {}
        for row in rows:
            team_id = row[0]
            if team_id is not None:
                result[team_id] = result.get(team_id, 0) + 1
        return result

    async def get_shootout_goals_for_fixture(self, fixture_id: int) -> dict[int, int]:
        stmt = (
            select(PlayerEvent.team_id)
            .where(
                PlayerEvent.fixture_id == fixture_id,
                PlayerEvent.event_type == EventType.GOAL_SHOOTOUT,
            )
        )
        rows = (await self._session.execute(stmt)).all()
        result: dict[int, int] = {}
        for row in rows:
            team_id = row[0]
            if team_id is not None:
                result[team_id] = result.get(team_id, 0) + 1
        return result

    async def get_competition_name(self, competition_id: int) -> str:
        stmt = select(Competition.name).where(Competition.id == competition_id)
        name = (await self._session.execute(stmt)).scalar_one_or_none()
        if name is None:
            raise ValueError(f"Competition {competition_id} not found")
        return name

    async def get_all_knockout_competition_ids(self, season: str) -> list[int]:
        stmt = (
            select(distinct(Fixture.competition_id))
            .where(
                Fixture.season == season,
                Fixture.stage != "regular",
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [row[0] for row in rows]
