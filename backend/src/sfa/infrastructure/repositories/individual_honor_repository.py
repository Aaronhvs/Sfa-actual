from __future__ import annotations

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.individual_honors import (
    HonorCandidateStats,
    HonorCompetitionDTO,
    IndividualHonor,
    IndividualHonorRepositoryPort,
    PlayerIndividualHonorDTO,
)
from sfa.domain.season_scope import AwardPeriodScope
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.individual_honors.models import IndividualHonorModel
from sfa.infrastructure.models.player_stats.models import PlayerStats


def _scope_filter(scope: AwardPeriodScope):
    return or_(
        *[
            and_(
                Fixture.season == source.season,
                Fixture.competition_id.in_(source.competition_ids),
            )
            for source in scope.sources
        ]
    )


class IndividualHonorRepository(IndividualHonorRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_competitions_for_scope(
        self, scope: AwardPeriodScope
    ) -> list[HonorCompetitionDTO]:
        competition_ids = sorted({competition_id for _, competition_id in scope.pairs})
        rows = (
            await self._session.execute(
                select(Competition.id, Competition.name).where(
                    Competition.id.in_(competition_ids)
                )
            )
        ).all()
        names = {int(row[0]): str(row[1]) for row in rows}
        return [
            HonorCompetitionDTO(
                competition_id=competition_id,
                competition_name=names[competition_id],
                season=season,
            )
            for season, competition_id in sorted(scope.pairs)
            if competition_id in names
        ]

    async def get_candidate_stats(
        self,
        scope: AwardPeriodScope,
        competition_id: int | None = None,
    ) -> list[HonorCandidateStats]:
        filters = [_scope_filter(scope)]
        if competition_id is not None:
            filters.append(Fixture.competition_id == competition_id)

        stmt = (
            select(
                PlayerStats.player_id,
                func.coalesce(func.sum(PlayerStats.goals), 0).label("goals"),
                func.coalesce(func.sum(PlayerStats.assists), 0).label("assists"),
                func.coalesce(func.sum(PlayerStats.minutes), 0).label("minutes"),
                func.coalesce(func.sum(PlayerStats.dribbles_won), 0).label("dribbles_won"),
                func.coalesce(func.sum(PlayerStats.dribbles_attempts), 0).label("dribbles_attempts"),
                func.coalesce(func.sum(PlayerStats.duels_won), 0).label("duels_won"),
                func.coalesce(func.sum(PlayerStats.duels_total), 0).label("duels_total"),
            )
            .join(Fixture, Fixture.id == PlayerStats.fixture_id)
            .where(*filters)
            .group_by(PlayerStats.player_id)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            HonorCandidateStats(
                player_id=int(row["player_id"]),
                goals=int(row["goals"]),
                assists=int(row["assists"]),
                minutes=int(row["minutes"]),
                dribbles_won=int(row["dribbles_won"]),
                dribbles_attempts=int(row["dribbles_attempts"]),
                duels_won=int(row["duels_won"]),
                duels_total=int(row["duels_total"]),
            )
            for row in rows
        ]

    async def replace_scope_honors(
        self,
        scope_key: str,
        rules_version_id: int,
        honors: list[IndividualHonor],
    ) -> None:
        await self._session.execute(
            delete(IndividualHonorModel).where(
                IndividualHonorModel.scope_key == scope_key,
                IndividualHonorModel.rules_version_id == rules_version_id,
            )
        )
        self._session.add_all([
            IndividualHonorModel(
                player_id=honor.player_id,
                scope_key=honor.scope_key,
                scope_label=honor.scope_label,
                context_key=honor.context_key,
                context_label=honor.context_label,
                scope_category=honor.scope_category.value,
                honor_type=honor.honor_type.value,
                source_season=honor.source_season,
                competition_id=honor.competition_id,
                rules_version_id=honor.rules_version_id,
                metric_value=honor.metric_value,
                metric_total=honor.metric_total,
                metric_rate=honor.metric_rate,
                raw_bonus_pts=honor.raw_bonus_pts,
                awarded_bonus_pts=honor.awarded_bonus_pts,
                calculation_details=honor.calculation_details,
            )
            for honor in honors
        ])
        await self._session.flush()

    async def get_player_honors(
        self,
        player_id: int,
        rules_version_id: int,
        scope_key: str | None = None,
    ) -> list[PlayerIndividualHonorDTO]:
        stmt = select(IndividualHonorModel).where(
            IndividualHonorModel.player_id == player_id,
            IndividualHonorModel.rules_version_id == rules_version_id,
        )
        if scope_key is not None:
            stmt = stmt.where(IndividualHonorModel.scope_key == scope_key)
        stmt = stmt.order_by(
            IndividualHonorModel.scope_key.desc(),
            IndividualHonorModel.awarded_bonus_pts.desc(),
            IndividualHonorModel.honor_type,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            PlayerIndividualHonorDTO(
                honor_id=row.id,
                honor_type=row.honor_type,
                scope_key=row.scope_key,
                scope_label=row.scope_label,
                context_label=row.context_label,
                source_season=row.source_season,
                competition_id=row.competition_id,
                metric_value=float(row.metric_value),
                metric_total=row.metric_total,
                metric_rate=float(row.metric_rate) if row.metric_rate is not None else None,
                bonus_pts=row.awarded_bonus_pts,
            )
            for row in rows
        ]
