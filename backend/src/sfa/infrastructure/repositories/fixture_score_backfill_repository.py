from __future__ import annotations

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from sfa.domain.ingestion_ports import FixtureScoreBackfillTargetDTO
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.teams.models import Team

FINAL_FIXTURE_STATUSES = ("FT", "AET", "PEN")


class FixtureScoreBackfillRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_missing_fixture_score_targets(
        self,
        seasons: list[str],
    ) -> list[FixtureScoreBackfillTargetDTO]:
        if not seasons:
            return []

        home_team = aliased(Team)
        away_team = aliased(Team)
        stmt = (
            select(
                Fixture.id,
                Fixture.external_id,
                Fixture.season,
                Fixture.status,
                home_team.external_id.label("home_team_external_id"),
                away_team.external_id.label("away_team_external_id"),
            )
            .join(home_team, home_team.id == Fixture.home_team_id)
            .join(away_team, away_team.id == Fixture.away_team_id)
            .where(
                Fixture.season.in_(seasons),
                Fixture.status.in_(FINAL_FIXTURE_STATUSES),
                or_(
                    Fixture.home_goals.is_(None),
                    Fixture.away_goals.is_(None),
                    Fixture.score_source.is_(None),
                ),
            )
            .order_by(Fixture.season, Fixture.external_id)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            FixtureScoreBackfillTargetDTO(
                fixture_id=row["id"],
                external_id=row["external_id"],
                season=row["season"],
                status=row["status"],
                home_team_external_id=row["home_team_external_id"],
                away_team_external_id=row["away_team_external_id"],
            )
            for row in rows
        ]

    async def update_fixture_score(
        self,
        fixture_id: int,
        status: str,
        home_goals: int,
        away_goals: int,
        score_source: str,
    ) -> None:
        result = await self._session.execute(
            update(Fixture)
            .where(Fixture.id == fixture_id)
            .values(
                status=status,
                home_goals=home_goals,
                away_goals=away_goals,
                score_source=score_source,
            )
        )
        if result.rowcount != 1:
            raise ValueError(f"Fixture not found during score backfill: {fixture_id}")
