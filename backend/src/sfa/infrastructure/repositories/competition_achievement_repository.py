from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.scoring.entities import CompetitionAchievement, PlayerAchievementBonus
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    LeagueChampionCandidateDTO,
    PlayerCompetitionAchievementDTO,
)
from sfa.domain.season_scope import AwardPeriodScope
from sfa.infrastructure.models.competition_achievements.models import (
    CompetitionAchievementModel,
    PlayerAchievementBonusModel,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.standings.models import StandingSnapshot
from sfa.infrastructure.models.teams.models import Team

_COMPLETED_FIXTURE_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}


class CompetitionAchievementRepository(CompetitionAchievementRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_achievement(self, achievement: CompetitionAchievement) -> int:
        stmt = (
            pg_insert(CompetitionAchievementModel)
            .values(
                competition_id=achievement.competition_id,
                team_id=achievement.team_id,
                season=achievement.season,
                phase=achievement.phase,
                bonus_points=achievement.bonus_points,
                weight=achievement.weight,
                created_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_competition_achievement",
                set_={
                    "bonus_points": achievement.bonus_points,
                    "weight": achievement.weight,
                },
            )
            .returning(CompetitionAchievementModel.id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def clear_achievement_bonuses(
        self,
        competition_id: int,
        season: str,
        rules_version_id: int,
    ) -> None:
        await self._session.execute(
            delete(PlayerAchievementBonusModel).where(
                PlayerAchievementBonusModel.competition_id == competition_id,
                PlayerAchievementBonusModel.season == season,
                PlayerAchievementBonusModel.rules_version_id == rules_version_id,
            )
        )
        await self._session.execute(
            update(SFASeasonScore)
            .where(
                SFASeasonScore.competition_id == competition_id,
                SFASeasonScore.season == season,
                SFASeasonScore.rules_version_id == rules_version_id,
            )
            .values(achievement_bonus_pts=0)
        )
        await self._session.flush()

    async def replace_achievement_for_phase(
        self, achievement: CompetitionAchievement
    ) -> int:
        stmt = delete(CompetitionAchievementModel).where(
            CompetitionAchievementModel.competition_id == achievement.competition_id,
            CompetitionAchievementModel.season == achievement.season,
            CompetitionAchievementModel.phase == achievement.phase,
            CompetitionAchievementModel.team_id != achievement.team_id,
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return await self.upsert_achievement(achievement)

    async def delete_achievements_for_competition_season(
        self, competition_id: int, season: str
    ) -> None:
        stmt = delete(CompetitionAchievementModel).where(
            CompetitionAchievementModel.competition_id == competition_id,
            CompetitionAchievementModel.season == season,
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_achievements_for_season(
        self, competition_id: int, season: str
    ) -> list[CompetitionAchievement]:
        stmt = select(CompetitionAchievementModel).where(
            CompetitionAchievementModel.competition_id == competition_id,
            CompetitionAchievementModel.season == season,
        )
        result = await self._session.execute(stmt)
        return [
            CompetitionAchievement(
                id=row.id,
                competition_id=row.competition_id,
                team_id=row.team_id,
                season=row.season,
                phase=row.phase,
                bonus_points=row.bonus_points,
                weight=float(row.weight),
                created_at=row.created_at,
            )
            for row in result.scalars().all()
        ]

    async def upsert_player_bonus(self, bonus: PlayerAchievementBonus) -> None:
        stmt = (
            pg_insert(PlayerAchievementBonusModel)
            .values(
                player_id=bonus.player_id,
                team_id=bonus.team_id,
                competition_id=bonus.competition_id,
                season=bonus.season,
                rules_version_id=bonus.rules_version_id,
                achievement_id=bonus.achievement_id,
                participation_ratio=bonus.participation_ratio,
                final_bonus=bonus.final_bonus,
                calculation_details=bonus.calculation_details,
                created_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_player_achievement_bonus",
                set_={
                    "participation_ratio": bonus.participation_ratio,
                    "final_bonus": bonus.final_bonus,
                    "calculation_details": bonus.calculation_details,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_team_total_minutes(
        self, team_id: int, competition_id: int, season: str
    ) -> int:
        # Returns fixtures_played × 90 so participation_ratio represents fraction
        # of full-time availability, not fraction of total squad minutes.
        stmt = (
            select(func.coalesce(func.count(func.distinct(Fixture.id)) * 90, 0))
            .select_from(PlayerStats)
            .join(Fixture, PlayerStats.fixture_id == Fixture.id)
            .where(
                PlayerStats.team_id == team_id,
                Fixture.competition_id == competition_id,
                Fixture.season == season,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_player_minutes_in_competition(
        self, player_id: int, competition_id: int, season: str
    ) -> int:
        stmt = (
            select(func.coalesce(func.sum(PlayerStats.minutes), 0))
            .join(Fixture, PlayerStats.fixture_id == Fixture.id)
            .where(
                PlayerStats.player_id == player_id,
                Fixture.competition_id == competition_id,
                Fixture.season == season,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_players_for_team_season(
        self, team_id: int, competition_id: int, season: str
    ) -> list[int]:
        stmt = (
            select(PlayerStats.player_id)
            .join(Fixture, PlayerStats.fixture_id == Fixture.id)
            .where(
                PlayerStats.team_id == team_id,
                Fixture.competition_id == competition_id,
                Fixture.season == season,
                PlayerStats.minutes > 0,
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def update_season_score_bonus(
        self,
        player_id: int,
        competition_id: int,
        season: str,
        rules_version_id: int,
        bonus_pts: float,
    ) -> None:
        stmt = (
            update(SFASeasonScore)
            .where(
                SFASeasonScore.player_id == player_id,
                SFASeasonScore.competition_id == competition_id,
                SFASeasonScore.season == season,
                SFASeasonScore.rules_version_id == rules_version_id,
            )
            .values(achievement_bonus_pts=bonus_pts)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_player_rank_in_team(
        self,
        player_id: int,
        team_id: int,
        competition_id: int,
        season: str,
        rules_version_id: int,
    ) -> int:
        ranked = (
            select(
                SFASeasonScore.player_id,
                func.rank().over(order_by=SFASeasonScore.total_pts.desc()).label("rn"),
            )
            .where(
                SFASeasonScore.team_id == team_id,
                SFASeasonScore.competition_id == competition_id,
                SFASeasonScore.season == season,
                SFASeasonScore.rules_version_id == rules_version_id,
            )
            .subquery()
        )
        stmt = select(ranked.c.rn).where(ranked.c.player_id == player_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return int(row) if row is not None else 12

    async def get_player_avg_rating(
        self,
        player_id: int,
        competition_id: int,
        season: str,
    ) -> float | None:
        stmt = (
            select(func.avg(PlayerStats.rating))
            .join(Fixture, PlayerStats.fixture_id == Fixture.id)
            .where(
                PlayerStats.player_id == player_id,
                Fixture.competition_id == competition_id,
                Fixture.season == season,
                PlayerStats.rating.is_not(None),
            )
        )
        result = await self._session.execute(stmt)
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None

    async def get_achievements_for_domestic_leagues(
        self, season: str, league_names: list[str]
    ) -> list[tuple[CompetitionAchievement, str]]:
        stmt = (
            select(
                CompetitionAchievementModel.id,
                CompetitionAchievementModel.competition_id,
                CompetitionAchievementModel.team_id,
                CompetitionAchievementModel.season,
                CompetitionAchievementModel.phase,
                CompetitionAchievementModel.bonus_points,
                CompetitionAchievementModel.weight,
                CompetitionAchievementModel.created_at,
                Competition.name.label("competition_name"),
            )
            .join(Competition, Competition.id == CompetitionAchievementModel.competition_id)
            .where(
                Competition.name.in_(league_names),
                CompetitionAchievementModel.season == season,
            )
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            (
                CompetitionAchievement(
                    id=row["id"],
                    competition_id=row["competition_id"],
                    team_id=row["team_id"],
                    season=row["season"],
                    phase=row["phase"],
                    bonus_points=row["bonus_points"],
                    weight=float(row["weight"]),
                    created_at=row["created_at"],
                ),
                row["competition_name"],
            )
            for row in rows
        ]

    async def get_domestic_league_leaders(
        self, season: str, league_names: list[str]
    ) -> list[LeagueChampionCandidateDTO]:
        latest_matchdays = (
            select(
                StandingSnapshot.competition_id,
                func.max(StandingSnapshot.matchday).label("matchday"),
            )
            .where(StandingSnapshot.season == season)
            .group_by(StandingSnapshot.competition_id)
            .subquery()
        )
        latest_rows = (
            select(
                StandingSnapshot.competition_id,
                StandingSnapshot.team_id,
                StandingSnapshot.season,
                StandingSnapshot.matchday,
                StandingSnapshot.position,
                func.count().over(
                    partition_by=StandingSnapshot.competition_id
                ).label("team_count"),
            )
            .join(
                latest_matchdays,
                and_(
                    latest_matchdays.c.competition_id
                    == StandingSnapshot.competition_id,
                    latest_matchdays.c.matchday == StandingSnapshot.matchday,
                ),
            )
            .where(StandingSnapshot.season == season)
            .subquery()
        )
        regular_fixture_counts = (
            select(
                Fixture.competition_id,
                func.count(Fixture.id).label("regular_fixture_count"),
                func.count(Fixture.id).filter(
                    ~Fixture.status.in_(_COMPLETED_FIXTURE_STATUSES)
                ).label("pending_fixture_count"),
            )
            .where(
                Fixture.season == season,
                Fixture.stage == "regular",
            )
            .group_by(Fixture.competition_id)
            .subquery()
        )
        stmt = (
            select(
                latest_rows.c.competition_id,
                Competition.name.label("competition_name"),
                latest_rows.c.team_id,
                latest_rows.c.season,
                latest_rows.c.matchday,
                latest_rows.c.team_count,
                func.coalesce(
                    regular_fixture_counts.c.regular_fixture_count, 0
                ).label("regular_fixture_count"),
                func.coalesce(
                    regular_fixture_counts.c.pending_fixture_count, 0
                ).label("pending_fixture_count"),
            )
            .join(Competition, Competition.id == latest_rows.c.competition_id)
            .outerjoin(
                regular_fixture_counts,
                regular_fixture_counts.c.competition_id
                == latest_rows.c.competition_id,
            )
            .where(
                Competition.name.in_(league_names),
                latest_rows.c.position == 1,
            )
            .order_by(Competition.name)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [LeagueChampionCandidateDTO(**dict(row)) for row in rows]

    async def get_competition_ids_for_season(self, season: str) -> list[int]:
        stmt = (
            select(CompetitionAchievementModel.competition_id)
            .where(CompetitionAchievementModel.season == season)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_player_achievements(
        self,
        player_id: int,
        rules_version_id: int,
        season: str | None = None,
        scope: AwardPeriodScope | None = None,
    ) -> list[PlayerCompetitionAchievementDTO]:
        stmt = (
            select(
                CompetitionAchievementModel.id.label("achievement_id"),
                CompetitionAchievementModel.competition_id,
                Competition.name.label("competition_name"),
                CompetitionAchievementModel.team_id,
                Team.name.label("team_name"),
                CompetitionAchievementModel.season,
                CompetitionAchievementModel.phase,
                PlayerAchievementBonusModel.final_bonus.label("bonus_pts"),
            )
            .join(
                PlayerAchievementBonusModel,
                PlayerAchievementBonusModel.achievement_id
                == CompetitionAchievementModel.id,
            )
            .join(
                Competition,
                Competition.id == CompetitionAchievementModel.competition_id,
            )
            .join(Team, Team.id == CompetitionAchievementModel.team_id)
            .where(
                PlayerAchievementBonusModel.player_id == player_id,
                PlayerAchievementBonusModel.rules_version_id == rules_version_id,
            )
            .order_by(
                CompetitionAchievementModel.season.desc(),
                Competition.name.asc(),
            )
        )
        if season is not None:
            stmt = stmt.where(CompetitionAchievementModel.season == season)
        if scope is not None:
            stmt = stmt.where(
                or_(
                    *[
                        and_(
                            CompetitionAchievementModel.season == source.season,
                            CompetitionAchievementModel.competition_id.in_(source.competition_ids),
                        )
                        for source in scope.sources
                    ]
                )
            )

        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            PlayerCompetitionAchievementDTO(
                achievement_id=row["achievement_id"],
                competition_id=row["competition_id"],
                competition_name=row["competition_name"],
                team_id=row["team_id"],
                team_name=row["team_name"],
                season=row["season"],
                phase=row["phase"],
                title_count=1 if row["phase"] in {"winner", "champion"} else 0,
                bonus_pts=float(row["bonus_pts"]),
            )
            for row in rows
        ]
