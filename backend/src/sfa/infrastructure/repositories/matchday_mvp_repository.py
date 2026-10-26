import hashlib
import re
from decimal import Decimal
from typing import Mapping

from sqlalchemy import and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.matchday_mvp import (
    FINAL_STATUSES,
    CompetitionPositionsProtocol,
    MatchdayMvpRepositoryProtocol,
    MvpPerformance,
)
from sfa.domain.ports import TournamentFixtureDTO, TournamentTeamDTO
from sfa.domain.season_scope import AwardPeriodScope
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixture_team_strengths.models import FixtureTeamStrength
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.teams.models import Team

DECISIVE_TYPES = (EventType.GOAL, EventType.GOAL_PENALTY, EventType.ASSIST, EventType.CORNER_ASSIST)


class MatchdayMvpRepository(MatchdayMvpRepositoryProtocol):
    def __init__(self, session: AsyncSession, positions: CompetitionPositionsProtocol) -> None:
        self._session, self._positions = session, positions

    async def competition_exists(self, competition_id: int) -> bool:
        return await self._session.scalar(select(Competition.id).where(Competition.id == competition_id)) is not None

    async def get_fixtures(self, competition_id: int, season: str) -> tuple[TournamentFixtureDTO, ...]:
        home, away = Team.__table__.alias("mvp_home"), Team.__table__.alias("mvp_away")
        rows = (await self._session.execute(
            select(Fixture, home.c.external_id.label("home_external"), home.c.name.label("home_name"),
                   away.c.external_id.label("away_external"), away.c.name.label("away_name"))
            .join(home, home.c.id == Fixture.home_team_id).join(away, away.c.id == Fixture.away_team_id)
            .where(Fixture.competition_id == competition_id, Fixture.season == season)
            .order_by(Fixture.played_at, Fixture.external_id)
        )).all()
        return tuple(TournamentFixtureDTO(
            row.Fixture.id, row.Fixture.external_id, competition_id, row.Fixture.stage, row.Fixture.matchday,
            row.Fixture.played_at, row.Fixture.status, row.Fixture.home_goals, row.Fixture.away_goals,
            TournamentTeamDTO(row.Fixture.home_team_id, row.home_external, row.home_name),
            TournamentTeamDTO(row.Fixture.away_team_id, row.away_external, row.away_name),
        ) for row in rows)

    async def get_performances(self, competition_id: int, season: str,
                               rules_version_id: int) -> tuple[MvpPerformance, ...]:
        fixture_filters = (Fixture.competition_id == competition_id, Fixture.season == season,
                           Fixture.status.in_(FINAL_STATUSES))
        points = (select(PlayerEventScore.player_id, PlayerEventScore.fixture_id,
                         func.sum(PlayerEventScore.final_points).label("points"))
                  .join(Fixture, Fixture.id == PlayerEventScore.fixture_id)
                  .where(*fixture_filters, PlayerEventScore.rules_version_id == rules_version_id,
                         PlayerEventScore.competition_id == competition_id, PlayerEventScore.season == season)
                  .group_by(PlayerEventScore.player_id, PlayerEventScore.fixture_id).subquery())
        event_team_valid = PlayerEvent.team_id.in_((Fixture.home_team_id, Fixture.away_team_id))
        events = (select(
            PlayerEvent.player_id, PlayerEvent.fixture_id,
            func.count(func.distinct(PlayerEvent.team_id)).label("team_count"),
            func.min(PlayerEvent.team_id).label("team_id"),
            func.sum(case((PlayerEvent.event_type.in_((EventType.GOAL, EventType.GOAL_PENALTY)), 1),
                          else_=0)).label("goals"),
            func.sum(case((PlayerEvent.event_type.in_((EventType.ASSIST, EventType.CORNER_ASSIST)), 1),
                          else_=0)).label("assists"),
        ).join(Fixture, Fixture.id == PlayerEvent.fixture_id).where(*fixture_filters, event_team_valid)
            .group_by(PlayerEvent.player_id, PlayerEvent.fixture_id).subquery())
        valid_stats = and_(PlayerStats.minutes > 0,
                           PlayerStats.team_id.in_((Fixture.home_team_id, Fixture.away_team_id)))
        team_id = case((valid_stats, PlayerStats.team_id), else_=events.c.team_id)
        opponent = case((team_id == Fixture.home_team_id, Fixture.away_team_id), else_=Fixture.home_team_id)
        statement = (select(
            points.c.player_id, points.c.fixture_id, points.c.points, Player.name, Player.photo_url,
            team_id.label("team_id"),
            case((valid_stats, PlayerStats.goals), else_=func.coalesce(events.c.goals, 0)).label("goals"),
            case((valid_stats, PlayerStats.assists), else_=func.coalesce(events.c.assists, 0)).label("assists"),
            FixtureTeamStrength.pre_match_strength.label("rival_strength"),
        ).select_from(points).join(Player, Player.id == points.c.player_id)
            .join(Fixture, Fixture.id == points.c.fixture_id)
            .outerjoin(PlayerStats, and_(PlayerStats.player_id == points.c.player_id,
                                        PlayerStats.fixture_id == points.c.fixture_id))
            .outerjoin(events, and_(events.c.player_id == points.c.player_id,
                                   events.c.fixture_id == points.c.fixture_id))
            .outerjoin(FixtureTeamStrength, and_(FixtureTeamStrength.fixture_id == Fixture.id,
                                                FixtureTeamStrength.team_id == opponent))
            .where(team_id.in_((Fixture.home_team_id, Fixture.away_team_id)),
                   func.coalesce(events.c.team_count, 0) <= 1,
                   or_(events.c.team_id.is_(None), events.c.team_id == team_id)))
        rows = (await self._session.execute(statement)).mappings().all()
        contexts = await self._decisive_contexts(competition_id, season, rules_version_id)
        return tuple(MvpPerformance(
            row["player_id"], row["fixture_id"], row["name"], row["photo_url"], row["team_id"],
            Decimal(row["points"]), int(row["goals"]), int(row["assists"]),
            contexts.get((row["player_id"], row["fixture_id"], row["team_id"])),
            float(row["rival_strength"]) if row["rival_strength"] is not None else None,
        ) for row in rows)

    async def _decisive_contexts(self, competition_id, season, rules_version_id):
        actions = (select(
            PlayerEvent.player_id, PlayerEvent.fixture_id, PlayerEvent.team_id, PlayerEvent.score_before,
            Fixture.home_team_id, Fixture.away_team_id,
            func.row_number().over(partition_by=(PlayerEvent.player_id, PlayerEvent.fixture_id),
                                   order_by=(PlayerEventScore.final_points.desc(), PlayerEvent.minute,
                                             PlayerEvent.id)).label("rn"),
        ).join(PlayerEventScore, PlayerEventScore.event_id == PlayerEvent.id)
            .join(Fixture, Fixture.id == PlayerEvent.fixture_id)
            .where(Fixture.competition_id == competition_id, Fixture.season == season,
                   Fixture.status.in_(FINAL_STATUSES), PlayerEventScore.rules_version_id == rules_version_id,
                   PlayerEvent.event_type.in_(DECISIVE_TYPES),
                   PlayerEventScore.action_type.in_([kind.value for kind in DECISIVE_TYPES])).subquery())
        rows = (await self._session.execute(select(actions).where(actions.c.rn == 1))).mappings().all()
        contexts = {}
        for row in rows:
            before = re.fullmatch(r"(\d+)[:\-](\d+)", row["score_before"] or "")
            if before and row["team_id"] in (row["home_team_id"], row["away_team_id"]):
                difference = int(before[1]) - int(before[2])
                if row["team_id"] == row["away_team_id"]:
                    difference = -difference
                contexts[(row["player_id"], row["fixture_id"], row["team_id"])] = difference
        return contexts

    async def get_positions(self, scope: AwardPeriodScope, competition_id: int) -> Mapping[int, str | None]:
        positions = await self._positions.get_competition_positions(scope, competition_id)
        return {player_id: position for (player_id, _, cid), position in positions.items() if cid == competition_id}

    async def get_data_stamp(self, scope: AwardPeriodScope, competition_id: int, season: str,
                             rules_version_id: int) -> str:
        # xmin changes on INSERT/UPDATE, including in-place recalculations with unchanged global sums.
        # The per-row hash also identifies deletes; no scoring JSON manifests are materialized.
        sources = (
            ("fixtures t", "t.competition_id=:competition AND t.season=:season",
             "t.id,t.stage,t.matchday,t.status,t.played_at,t.home_team_id,t.away_team_id,t.home_goals,t.away_goals"),
            ("player_event_scores t", "t.competition_id=:competition AND t.season=:season "
             "AND t.rules_version_id=:version", "t.id,t.player_id,t.fixture_id,t.action_type,t.final_points"),
            ("player_stats t JOIN fixtures f ON f.id=t.fixture_id",
             "f.competition_id=:competition AND f.season=:season",
             "t.id,t.player_id,t.fixture_id,t.team_id,t.minutes,t.goals,t.assists"),
            ("player_events t JOIN fixtures f ON f.id=t.fixture_id",
             "f.competition_id=:competition AND f.season=:season",
             "t.id,t.player_id,t.fixture_id,t.team_id,t.event_type,t.minute,t.score_before,t.score_diff"),
            ("fixture_team_strengths t", "t.competition_id=:competition AND t.season=:season",
             "t.fixture_id,t.team_id,t.pre_match_strength"),
            ("player_position_assignments t", "TRUE", "t.id,t.position,t.status,t.revision_id"),
            ("position_scope_classifications t", "t.scope_key=:scope", "t.id,t.position,t.batch_id"),
            ("position_correction_batches t", "TRUE", "t.batch_id,t.status"),
        )
        columns = []
        for source, predicate, fields in sources:
            columns.append(f"(SELECT coalesce(bit_xor(hashtextextended(ROW({fields},t.xmin::text)::text,0)),0) "
                           f"FROM {source} WHERE {predicate})")
        row = (await self._session.execute(text("SELECT " + ",".join(columns)), {
            "competition": competition_id, "season": season, "version": rules_version_id, "scope": scope.key,
        })).one()
        return hashlib.sha256("|".join(map(str, row)).encode()).hexdigest()[:24]
