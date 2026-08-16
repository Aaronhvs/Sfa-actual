from __future__ import annotations

from datetime import date

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import (
    TournamentCompetitionDTO,
    TournamentDetailDTO,
    TournamentFixtureDTO,
    TournamentFixtureGroupDTO,
    TournamentStandingDTO,
    TournamentTeamDTO,
)
from sfa.infrastructure.models.competition_achievements.models import (
    CompetitionAchievementModel,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.standings.models import StandingSnapshot
from sfa.infrastructure.models.teams.models import Team

FINAL_STATUSES = ("FT", "AET", "PEN")


def _fixture_dto(row) -> TournamentFixtureDTO:
    return TournamentFixtureDTO(
        id=row["id"],
        external_id=row["external_id"],
        competition_id=row["competition_id"],
        stage=row["stage"],
        matchday=row["matchday"],
        played_at=row["played_at"],
        status=row["status"],
        home_goals=row["home_goals"],
        away_goals=row["away_goals"],
        home_team=TournamentTeamDTO(
            id=row["home_team_id"],
            external_id=row["home_team_external_id"],
            name=row["home_team_name"],
        ),
        away_team=TournamentTeamDTO(
            id=row["away_team_id"],
            external_id=row["away_team_external_id"],
            name=row["away_team_name"],
        ),
        competition_name=row.get("competition_name"),
    )


class TournamentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_latest_season(self) -> str | None:
        return await self._session.scalar(
            select(func.max(Fixture.season))
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(Competition.participant_kind == "club")
        )

    async def list_competitions(
        self, season: str,
    ) -> list[TournamentCompetitionDTO]:
        completed = func.sum(
            case((Fixture.status.in_(FINAL_STATUSES), 1), else_=0)
        )
        stmt = (
            select(
                Competition.id,
                Competition.name,
                Competition.country,
                Competition.participant_kind,
                func.count(Fixture.id).label("total_fixtures"),
                completed.label("completed_fixtures"),
            )
            .join(Fixture, Fixture.competition_id == Competition.id)
            .where(
                Fixture.season == season,
                Competition.participant_kind == "club",
            )
            .group_by(
                Competition.id,
                Competition.name,
                Competition.country,
                Competition.participant_kind,
            )
            .order_by(Competition.name)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            TournamentCompetitionDTO(
                id=row["id"],
                name=row["name"],
                country=row["country"],
                season=season,
                participant_kind=row["participant_kind"],
                total_fixtures=int(row["total_fixtures"]),
                completed_fixtures=int(row["completed_fixtures"] or 0),
                upcoming_fixtures=(
                    int(row["total_fixtures"])
                    - int(row["completed_fixtures"] or 0)
                ),
            )
            for row in rows
        ]

    async def get_tournament(
        self, competition_id: int, season: str,
    ) -> TournamentDetailDTO | None:
        competitions = await self.list_competitions(season)
        competition = next(
            (item for item in competitions if item.id == competition_id),
            None,
        )
        if competition is None:
            return None

        home = Team.__table__.alias("home_team")
        away = Team.__table__.alias("away_team")
        fixture_stmt = (
            select(
                Fixture.id,
                Fixture.external_id,
                Fixture.competition_id,
                Fixture.stage,
                Fixture.matchday,
                Fixture.played_at,
                Fixture.status,
                Fixture.home_goals,
                Fixture.away_goals,
                Competition.name.label("competition_name"),
                home.c.id.label("home_team_id"),
                home.c.external_id.label("home_team_external_id"),
                home.c.name.label("home_team_name"),
                away.c.id.label("away_team_id"),
                away.c.external_id.label("away_team_external_id"),
                away.c.name.label("away_team_name"),
            )
            .join(home, home.c.id == Fixture.home_team_id)
            .join(away, away.c.id == Fixture.away_team_id)
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(
                Fixture.competition_id == competition_id,
                Fixture.season == season,
            )
            .order_by(Fixture.played_at, Fixture.id)
        )
        fixture_rows = (await self._session.execute(fixture_stmt)).mappings().all()
        fixtures = tuple(_fixture_dto(row) for row in fixture_rows)

        matchday = await self._session.scalar(
            select(func.max(StandingSnapshot.matchday)).where(
                StandingSnapshot.competition_id == competition_id,
                StandingSnapshot.season == season,
            )
        )
        standings: tuple[TournamentStandingDTO, ...] = ()
        if matchday is not None:
            standing_stmt = (
                select(
                    StandingSnapshot.position,
                    StandingSnapshot.points,
                    Team.id.label("team_id"),
                    Team.external_id.label("team_external_id"),
                    Team.name.label("team_name"),
                )
                .join(Team, Team.id == StandingSnapshot.team_id)
                .where(
                    StandingSnapshot.competition_id == competition_id,
                    StandingSnapshot.season == season,
                    StandingSnapshot.matchday == matchday,
                )
                .order_by(StandingSnapshot.position)
            )
            rows = (await self._session.execute(standing_stmt)).mappings().all()
            standings = tuple(
                TournamentStandingDTO(
                    position=row["position"],
                    points=row["points"],
                    team=TournamentTeamDTO(
                        id=row["team_id"],
                        external_id=row["team_external_id"],
                        name=row["team_name"],
                    ),
                )
                for row in rows
            )

        champion_row = (
            await self._session.execute(
                select(
                    Team.id.label("team_id"),
                    Team.external_id.label("team_external_id"),
                    Team.name.label("team_name"),
                )
                .join(
                    CompetitionAchievementModel,
                    CompetitionAchievementModel.team_id == Team.id,
                )
                .where(
                    CompetitionAchievementModel.competition_id == competition_id,
                    CompetitionAchievementModel.season == season,
                    CompetitionAchievementModel.phase == "winner",
                )
                .order_by(CompetitionAchievementModel.created_at.desc())
                .limit(1)
            )
        ).mappings().first()
        champion = None
        if champion_row is not None:
            champion = TournamentTeamDTO(
                id=champion_row["team_id"],
                external_id=champion_row["team_external_id"],
                name=champion_row["team_name"],
            )

        return TournamentDetailDTO(
            competition=competition,
            standings_matchday=matchday,
            fixtures=fixtures,
            standings=standings,
            champion=champion,
        )

    async def list_fixture_dates(self, season: str) -> list[date]:
        fixture_day = cast(Fixture.played_at, Date)
        stmt = (
            select(fixture_day.label("fixture_date"))
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(
                Fixture.season == season,
                Competition.participant_kind == "club",
            )
            .distinct()
            .order_by(fixture_day)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows)

    async def get_fixture_groups(
        self,
        season: str,
        fixture_date: date,
    ) -> list[TournamentFixtureGroupDTO]:
        competitions = {
            item.id: item for item in await self.list_competitions(season)
        }
        home = Team.__table__.alias("dashboard_home_team")
        away = Team.__table__.alias("dashboard_away_team")
        stmt = (
            select(
                Fixture.id,
                Fixture.external_id,
                Fixture.competition_id,
                Fixture.stage,
                Fixture.matchday,
                Fixture.played_at,
                Fixture.status,
                Fixture.home_goals,
                Fixture.away_goals,
                Competition.name.label("competition_name"),
                home.c.id.label("home_team_id"),
                home.c.external_id.label("home_team_external_id"),
                home.c.name.label("home_team_name"),
                away.c.id.label("away_team_id"),
                away.c.external_id.label("away_team_external_id"),
                away.c.name.label("away_team_name"),
            )
            .join(home, home.c.id == Fixture.home_team_id)
            .join(away, away.c.id == Fixture.away_team_id)
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(
                Fixture.season == season,
                Competition.participant_kind == "club",
                cast(Fixture.played_at, Date) == fixture_date,
            )
            .order_by(Fixture.played_at, Fixture.id)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        grouped: dict[int, list[TournamentFixtureDTO]] = {}
        for row in rows:
            grouped.setdefault(row["competition_id"], []).append(
                _fixture_dto(row)
            )
        return [
            TournamentFixtureGroupDTO(
                competition=competitions[competition_id],
                fixtures=tuple(fixtures),
            )
            for competition_id, fixtures in grouped.items()
            if competition_id in competitions
        ]

    async def get_fixture_by_external_id(
        self,
        fixture_external_id: int,
        season: str,
    ) -> TournamentFixtureDTO | None:
        home = Team.__table__.alias("fixture_detail_home_team")
        away = Team.__table__.alias("fixture_detail_away_team")
        stmt = (
            select(
                Fixture.id,
                Fixture.external_id,
                Fixture.competition_id,
                Fixture.stage,
                Fixture.matchday,
                Fixture.played_at,
                Fixture.status,
                Fixture.home_goals,
                Fixture.away_goals,
                Competition.name.label("competition_name"),
                home.c.id.label("home_team_id"),
                home.c.external_id.label("home_team_external_id"),
                home.c.name.label("home_team_name"),
                away.c.id.label("away_team_id"),
                away.c.external_id.label("away_team_external_id"),
                away.c.name.label("away_team_name"),
            )
            .join(home, home.c.id == Fixture.home_team_id)
            .join(away, away.c.id == Fixture.away_team_id)
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(
                Fixture.external_id == fixture_external_id,
                Fixture.season == season,
                Competition.participant_kind == "club",
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).mappings().first()
        return _fixture_dto(row) if row is not None else None
