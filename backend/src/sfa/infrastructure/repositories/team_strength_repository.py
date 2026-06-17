from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.scoring_ports import (
    FixtureEloRow,
    TeamCompetitionRow,
    TeamEloRow,
    TeamStandingRow,
    TeamStrengthCoverageRow,
    TeamStrengthRepositoryPort,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.standings.models import StandingSnapshot
from sfa.infrastructure.models.team_strengths.models import TeamStrength
from sfa.infrastructure.models.teams.models import Team

logger = logging.getLogger(__name__)


class TeamStrengthRepository(TeamStrengthRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_team_strength(
        self, team_id: int, season: str, competition_id: int
    ) -> float | None:
        stmt = select(TeamStrength.strength).where(
            TeamStrength.team_id == team_id,
            TeamStrength.season == season,
            TeamStrength.competition_id == competition_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return float(row) if row is not None else None

    async def upsert_team_strength(
        self,
        team_id: int,
        season: str,
        competition_id: int,
        strength: float,
        source: str,
    ) -> None:
        stmt = (
            pg_insert(TeamStrength)
            .values(
                team_id=team_id,
                season=season,
                competition_id=competition_id,
                strength=strength,
                source=source,
                created_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_team_strength",
                set_={"strength": strength, "source": source, "elo_raw": None},
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_team_standings_for_season(
        self, competition_id: int, season: str
    ) -> list[TeamStandingRow]:
        stmt = (
            select(
                StandingSnapshot.team_id,
                func.avg(StandingSnapshot.position).label("avg_position"),
                func.max(StandingSnapshot.points).label("total_points"),
                func.count(StandingSnapshot.matchday.distinct()).label("matchdays_played"),
            )
            .where(
                StandingSnapshot.competition_id == competition_id,
                StandingSnapshot.season == season,
            )
            .group_by(StandingSnapshot.team_id)
        )
        result = await self._session.execute(stmt)
        return [
            TeamStandingRow(
                team_id=row.team_id,
                season=season,
                competition_id=competition_id,
                avg_position=float(row.avg_position),
                total_points=int(row.total_points),
                matchdays_played=int(row.matchdays_played),
            )
            for row in result.all()
        ]

    async def get_team_strength_with_elo(
        self, team_id: int, season: str, competition_id: int
    ) -> tuple[float | None, float | None]:
        stmt = select(TeamStrength.strength, TeamStrength.elo_raw).where(
            TeamStrength.team_id == team_id,
            TeamStrength.season == season,
            TeamStrength.competition_id == competition_id,
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None, None
        return (
            float(row.strength) if row.strength is not None else None,
            float(row.elo_raw) if row.elo_raw is not None else None,
        )

    async def upsert_team_elo(
        self,
        team_id: int,
        season: str,
        elo_raw: float,
        strength_normalized: float,
        source: str,
        competition_ids: list[int],
    ) -> None:
        if not competition_ids:
            logger.warning(
                "[TeamStrengthRepository] No competition_ids for team_id=%d season=%s; skipping ELO upsert",
                team_id,
                season,
            )
            return

        now = datetime.now(timezone.utc)
        for competition_id in competition_ids:
            stmt = (
                pg_insert(TeamStrength)
                .values(
                    team_id=team_id,
                    season=season,
                    competition_id=competition_id,
                    strength=strength_normalized,
                    elo_raw=elo_raw,
                    source=source,
                    created_at=now,
                )
                .on_conflict_do_update(
                    constraint="uq_team_strength",
                    set_={
                        "strength": strength_normalized,
                        "elo_raw": elo_raw,
                        "source": source,
                    },
                )
            )
            await self._session.execute(stmt)
        await self._session.flush()

    async def get_all_teams_with_elo(self, season: str) -> list[TeamEloRow]:
        stmt = (
            select(
                TeamStrength.team_id,
                TeamStrength.season,
                func.max(TeamStrength.elo_raw).label("elo_raw"),
                func.max(TeamStrength.strength).label("strength"),
            )
            .where(
                TeamStrength.season == season,
                TeamStrength.elo_raw.is_not(None),
            )
            .group_by(TeamStrength.team_id, TeamStrength.season)
        )
        result = await self._session.execute(stmt)
        return [
            TeamEloRow(
                team_id=row.team_id,
                season=row.season,
                elo_raw=float(row.elo_raw),
                strength=float(row.strength),
            )
            for row in result.all()
        ]

    async def get_fixtures_for_elo_recalc(
        self, season: str, competition_ids: list[int]
    ) -> list[FixtureEloRow]:
        if not competition_ids:
            return []

        resolved_team = func.coalesce(
            PlayerStats.team_id,
            case(
                (Player.team_id == Fixture.home_team_id, Fixture.home_team_id),
                (Player.team_id == Fixture.away_team_id, Fixture.away_team_id),
                else_=None,
            ),
        )
        home_goals_expr = func.coalesce(
            func.sum(case((resolved_team == Fixture.home_team_id, PlayerStats.goals), else_=0)),
            0,
        ).label("home_goals")
        away_goals_expr = func.coalesce(
            func.sum(case((resolved_team == Fixture.away_team_id, PlayerStats.goals), else_=0)),
            0,
        ).label("away_goals")
        unresolved_expr = func.sum(
            case((resolved_team.is_(None), 1), else_=0)
        ).label("unresolved_players")

        stmt = (
            select(
                Fixture.id.label("fixture_id"),
                Fixture.home_team_id,
                Fixture.away_team_id,
                Fixture.played_at,
                Fixture.competition_id,
                Fixture.season,
                home_goals_expr,
                away_goals_expr,
                unresolved_expr,
            )
            .join(PlayerStats, PlayerStats.fixture_id == Fixture.id)
            .join(Player, Player.id == PlayerStats.player_id)
            .where(
                Fixture.competition_id.in_(competition_ids),
                Fixture.season == season,
            )
            .group_by(
                Fixture.id,
                Fixture.home_team_id,
                Fixture.away_team_id,
                Fixture.played_at,
                Fixture.competition_id,
                Fixture.season,
            )
            .order_by(Fixture.played_at.asc().nulls_last())
        )
        result = await self._session.execute(stmt)
        rows: list[FixtureEloRow] = []
        for row in result.all():
            if int(row.unresolved_players or 0) > 0:
                logger.warning(
                    "[TeamStrengthRepository] Excluding fixture_id=%d from ELO: "
                    "%d player appearances have no valid team snapshot",
                    row.fixture_id,
                    int(row.unresolved_players),
                )
                continue
            rows.append(FixtureEloRow(
                fixture_id=row.fixture_id,
                home_team_id=row.home_team_id,
                away_team_id=row.away_team_id,
                played_at=row.played_at,
                competition_id=row.competition_id,
                home_goals=int(row.home_goals),
                away_goals=int(row.away_goals),
                season=row.season,
            ))
        return rows

    async def get_team_name_id_map(self, season: str) -> dict[str, int]:
        stmt = (
            select(Team.name, Team.id)
            .join(
                Fixture,
                or_(
                    Fixture.home_team_id == Team.id,
                    Fixture.away_team_id == Team.id,
                ),
            )
            .where(Fixture.season == season)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return {row.name: row.id for row in result.all()}

    async def get_active_competition_ids_for_team(
        self, team_id: int, season: str
    ) -> list[int]:
        stmt = (
            select(Fixture.competition_id)
            .where(
                Fixture.season == season,
                or_(
                    Fixture.home_team_id == team_id,
                    Fixture.away_team_id == team_id,
                ),
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_competition_id_by_name(self, name: str) -> int | None:
        stmt = (
            select(Competition.id)
            .where(func.lower(Competition.name) == name.lower())
            .order_by(Competition.id.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_teams_for_competition_season(
        self, competition_id: int, season: str
    ) -> list[TeamCompetitionRow]:
        stmt = (
            select(
                Team.id.label("team_id"),
                Team.name.label("team_name"),
                Fixture.competition_id,
            )
            .join(
                Fixture,
                or_(
                    Fixture.home_team_id == Team.id,
                    Fixture.away_team_id == Team.id,
                ),
            )
            .where(
                Fixture.competition_id == competition_id,
                Fixture.season == season,
            )
            .distinct()
            .order_by(Team.name.asc())
        )
        result = await self._session.execute(stmt)
        return [
            TeamCompetitionRow(
                team_id=row.team_id,
                team_name=row.team_name,
                competition_id=row.competition_id,
            )
            for row in result.all()
        ]

    async def get_team_strength_coverage(
        self, competition_id: int, season: str
    ) -> list[TeamStrengthCoverageRow]:
        stmt = (
            select(
                Team.id.label("team_id"),
                Team.name.label("team_name"),
                Fixture.competition_id,
                TeamStrength.strength,
                TeamStrength.elo_raw,
                TeamStrength.source,
            )
            .join(
                Fixture,
                or_(
                    Fixture.home_team_id == Team.id,
                    Fixture.away_team_id == Team.id,
                ),
            )
            .outerjoin(
                TeamStrength,
                (TeamStrength.team_id == Team.id)
                & (TeamStrength.season == season)
                & (TeamStrength.competition_id == competition_id),
            )
            .where(
                Fixture.competition_id == competition_id,
                Fixture.season == season,
            )
            .distinct()
            .order_by(Team.name.asc())
        )
        result = await self._session.execute(stmt)
        return [
            TeamStrengthCoverageRow(
                team_id=row.team_id,
                team_name=row.team_name,
                competition_id=row.competition_id,
                strength=float(row.strength) if row.strength is not None else None,
                elo_raw=float(row.elo_raw) if row.elo_raw is not None else None,
                source=row.source,
            )
            for row in result.all()
        ]
