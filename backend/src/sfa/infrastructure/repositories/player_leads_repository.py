import hashlib
import logging
from typing import Mapping, Sequence

from sqlalchemy import and_, case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from sfa.domain.player_leads import LeadPolicy, LeadSample, PlayerLeadsRepositoryProtocol
from sfa.domain.season_scope import AwardPeriodScope, InconsistentScopeRulesVersionError, ScopeKind
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixture_team_strengths.models import FixtureTeamStrength
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.teams.models import Team
from sfa.infrastructure.repositories.position_projection import scope_position, scope_reference_position
from sfa.infrastructure.repositories.sfa_score_repository import (
    SFAScoreRepository,
    _latest_verified_team,
    _legacy_position_expression,
    _scope_filter,
)

logger = logging.getLogger(__name__)

FINAL_STATUSES = ("FT", "AET", "PEN")


def _verified_appearance_filters(scope: AwardPeriodScope) -> list:
    """Same population as scoring: finished fixtures, real minutes, a team that actually played the fixture."""
    return [
        Fixture.status.in_(FINAL_STATUSES),
        PlayerStats.minutes > 0,
        PlayerStats.team_id.is_not(None),
        or_(PlayerStats.team_id == Fixture.home_team_id, PlayerStats.team_id == Fixture.away_team_id),
        _scope_filter(Fixture, scope),
    ]


def _points_subquery(scope: AwardPeriodScope, rules_version_id: int | None):
    """SFA points per player and fixture for the resolved rules version."""
    if rules_version_id is None:
        return None
    return (
        select(
            PlayerEventScore.player_id,
            PlayerEventScore.fixture_id,
            func.sum(PlayerEventScore.final_points).label("points"),
        )
        .where(PlayerEventScore.rules_version_id == rules_version_id, _scope_filter(PlayerEventScore, scope))
        .group_by(PlayerEventScore.player_id, PlayerEventScore.fixture_id)
        .subquery()
    )


class PlayerLeadsRepository(PlayerLeadsRepositoryProtocol):
    def __init__(self, session: AsyncSession, policy: LeadPolicy | None = None) -> None:
        self._session = session
        self._policy = policy or LeadPolicy()

    async def get_competition_samples(
        self, scope: AwardPeriodScope, rules_version_id: int | None,
    ) -> Sequence[LeadSample]:
        penalties = (
            select(PlayerEvent.player_id, PlayerEvent.fixture_id, func.count().label("penalty_goals"))
            .where(PlayerEvent.event_type == EventType.GOAL_PENALTY)
            .group_by(PlayerEvent.player_id, PlayerEvent.fixture_id)
            .subquery()
        )
        rival = aliased(FixtureTeamStrength)
        opponent_id = case(
            (PlayerStats.team_id == Fixture.home_team_id, Fixture.away_team_id), else_=Fixture.home_team_id,
        )
        # A penalty event can only remove a goal the provider actually counted.
        penalty_used = func.least(func.coalesce(penalties.c.penalty_goals, 0), PlayerStats.goals)
        np_goals = PlayerStats.goals - penalty_used
        points = _points_subquery(scope, rules_version_id)

        statement = (
            select(
                PlayerStats.player_id,
                Fixture.season,
                Fixture.competition_id,
                Competition.name.label("competition_name"),
                Competition.participant_kind,
                func.sum(PlayerStats.minutes).label("minutes"),
                func.count(PlayerStats.id).label("matches"),
                func.sum(PlayerStats.goals).label("goals"),
                func.sum(PlayerStats.assists).label("assists"),
                func.sum(np_goals).label("np_goals"),
                # Rows where the provider reports more goals than shots on target are lifted to the goal count.
                func.sum(func.greatest(PlayerStats.shots_on - penalty_used, np_goals)).label("np_shots_on"),
                func.sum(penalty_used).label("penalty_goals"),
                func.sum(PlayerStats.shots_on).label("shots_on"),
                func.sum(PlayerStats.shots_total).label("shots_total"),
                func.sum(PlayerStats.passes_key).label("passes_key"),
                func.sum(PlayerStats.dribbles_won).label("dribbles_won"),
                func.sum(func.greatest(PlayerStats.dribbles_attempts, PlayerStats.dribbles_won))
                .label("dribbles_attempts"),
                func.sum(PlayerStats.duels_won).label("duels_won"),
                func.sum(func.greatest(PlayerStats.duels_total, PlayerStats.duels_won)).label("duels_total"),
                func.sum(PlayerStats.tackles_won).label("tackles"),
                func.sum(PlayerStats.interceptions).label("interceptions"),
                func.sum(PlayerStats.saves).label("saves"),
                func.sum(PlayerStats.goals_conceded).label("goals_conceded"),
                *self._big_game_columns(rival, points),
                func.sum(case((PlayerStats.goals > PlayerStats.shots_on, 1), else_=0)).label("corrected_rows"),
            )
            .select_from(PlayerStats)
            .join(Fixture, Fixture.id == PlayerStats.fixture_id)
            .join(Competition, Competition.id == Fixture.competition_id)
            .outerjoin(penalties, and_(
                penalties.c.player_id == PlayerStats.player_id, penalties.c.fixture_id == PlayerStats.fixture_id,
            ))
            .outerjoin(rival, and_(rival.fixture_id == Fixture.id, rival.team_id == opponent_id))
            .where(*_verified_appearance_filters(scope))
            .group_by(
                PlayerStats.player_id, Fixture.season, Fixture.competition_id,
                Competition.name, Competition.participant_kind,
            )
        )
        if points is not None:
            statement = statement.outerjoin(points, and_(
                points.c.player_id == PlayerStats.player_id, points.c.fixture_id == PlayerStats.fixture_id,
            ))

        rows = (await self._session.execute(statement)).mappings().all()
        positions = await self._competition_positions(scope)
        corrected = sum(int(row["corrected_rows"] or 0) for row in rows)
        if corrected:
            logger.info(
                "[PlayerLeadsRepository] %d appearance rows had more goals than shots on target in %s",
                corrected, scope.key,
            )
        return [
            LeadSample(
                player_id=row["player_id"],
                season=row["season"],
                competition_id=row["competition_id"],
                competition_name=row["competition_name"],
                participant_kind=row["participant_kind"],
                position=positions.get((row["player_id"], row["season"], row["competition_id"])),
                minutes=int(row["minutes"] or 0),
                matches=int(row["matches"] or 0),
                goals=int(row["goals"] or 0),
                assists=int(row["assists"] or 0),
                np_goals=int(row["np_goals"] or 0),
                np_shots_on=int(row["np_shots_on"] or 0),
                penalty_goals=int(row["penalty_goals"] or 0),
                shots_on=int(row["shots_on"] or 0),
                shots_total=int(row["shots_total"] or 0),
                passes_key=int(row["passes_key"] or 0),
                dribbles_won=int(row["dribbles_won"] or 0),
                dribbles_attempts=int(row["dribbles_attempts"] or 0),
                duels_won=int(row["duels_won"] or 0),
                duels_total=int(row["duels_total"] or 0),
                tackles=int(row["tackles"] or 0),
                interceptions=int(row["interceptions"] or 0),
                saves=int(row["saves"] or 0),
                goals_conceded=int(row["goals_conceded"] or 0),
                big_points=float(row["big_points"] or 0),
                big_minutes=int(row["big_minutes"] or 0),
                big_matches=int(row["big_matches"] or 0),
                elite_matches=int(row["elite_matches"] or 0),
            )
            for row in rows
        ]

    def _big_game_columns(self, rival, points) -> list:
        """Fixtures against Alto/Élite rivals (pre-match strength); zeros when no rules version is known."""
        if points is None:
            return [literal(0).label(name) for name in ("big_points", "big_minutes", "big_matches", "elite_matches")]
        big = and_(rival.pre_match_strength.is_not(None), rival.pre_match_strength >= self._policy.big_strength)
        elite = and_(rival.pre_match_strength.is_not(None), rival.pre_match_strength >= self._policy.elite_strength)
        return [
            func.sum(case((big, func.coalesce(points.c.points, 0)), else_=0)).label("big_points"),
            func.sum(case((big, PlayerStats.minutes), else_=0)).label("big_minutes"),
            func.sum(case((big, 1), else_=0)).label("big_matches"),
            func.sum(case((elite, 1), else_=0)).label("elite_matches"),
        ]

    async def _competition_positions(self, scope: AwardPeriodScope) -> dict[tuple[int, str, int], str | None]:
        """Use the deployed ranking's published scope and habitual-role projection."""
        ranked = (
            select(
                PlayerStats.player_id,
                Fixture.season,
                Fixture.competition_id,
                PlayerStats.team_id,
                func.row_number().over(
                    partition_by=(PlayerStats.player_id, Fixture.season, Fixture.competition_id),
                    order_by=(Fixture.played_at.desc(), Fixture.id.desc(), PlayerStats.id.desc()),
                ).label("rn"),
            )
            .join(Fixture, Fixture.id == PlayerStats.fixture_id)
            .where(
                _scope_filter(Fixture, scope),
                PlayerStats.team_id.is_not(None),
                PlayerStats.team_id.in_((Fixture.home_team_id, Fixture.away_team_id)),
            )
            .subquery()
        )
        rows = []
        # A concrete competition matches the ranking helper's contract and
        # avoids accidentally embedding the outer population in its subquery.
        for competition_id in sorted({c for source in scope.sources for c in source.competition_ids}):
            statement = (
                select(
                    ranked.c.player_id, ranked.c.season, ranked.c.competition_id,
                    scope_position(scope, competition_id, scope_reference_position(
                        scope=scope, season=scope.sources[0].season, team_id=Team.id,
                        competition_id=competition_id,
                        fallback=_legacy_position_expression(Team.name, competition_id),
                    )).label("position"),
                )
                .join(Team, Team.id == ranked.c.team_id)
                .join(Player, Player.id == ranked.c.player_id)
                .where(ranked.c.rn == 1, ranked.c.competition_id == competition_id)
            )
            rows.extend((await self._session.execute(statement)).all())
        return {
            (player_id, season, competition_id): position
            for player_id, season, competition_id, position in rows
        }

    async def get_scope_positions(self, scope: AwardPeriodScope) -> Mapping[int, str | None]:
        if scope.kind != ScopeKind.AWARD_PERIOD:
            return {}
        latest = _latest_verified_team(scope.sources[0].season, scope=scope)
        # Match the ranking's highest-scoring club competition fallback context.
        try:
            version = await SFAScoreRepository(self._session).resolve_rules_version_id_for_scope(scope)
        except InconsistentScopeRulesVersionError:
            version = None
        score_filters = [_scope_filter(SFASeasonScore, scope)]
        if version is not None:
            score_filters.append(SFASeasonScore.rules_version_id == version)
        best_competition = (
            select(SFASeasonScore.competition_id)
            .join(Competition, Competition.id == SFASeasonScore.competition_id)
            .where(SFASeasonScore.player_id == Player.id, *score_filters)
            .order_by(case((Competition.participant_kind == "club", 0), else_=1).asc(),
                      SFASeasonScore.total_pts.desc())
            .limit(1).correlate(Player).scalar_subquery()
        )
        statement = (
            select(latest.c.player_id, scope_position(scope, None, scope_reference_position(
                scope=scope, season=scope.sources[0].season, team_id=Team.id,
                competition_id=best_competition,
                fallback=_legacy_position_expression(Team.name, best_competition),
            )).label("position"))
            .join(Team, Team.id == latest.c.display_team_id)
            .join(Player, Player.id == latest.c.player_id)
        )
        rows = (await self._session.execute(statement)).all()
        return {player_id: position for player_id, position in rows}

    async def get_data_stamp(self, scope: AwardPeriodScope, rules_version_id: int | None) -> str:
        score_filters = [_scope_filter(SFASeasonScore, scope)]
        if rules_version_id is not None:
            score_filters.append(SFASeasonScore.rules_version_id == rules_version_id)
        last_updated, score_rows = (await self._session.execute(
            select(func.max(SFASeasonScore.last_updated), func.count(SFASeasonScore.id)).where(*score_filters)
        )).one()
        last_fixture = (await self._session.execute(
            select(func.max(Fixture.id)).where(_scope_filter(Fixture, scope), Fixture.status.in_(FINAL_STATUSES))
        )).scalar_one_or_none()
        raw = f"{last_updated.isoformat() if last_updated else 'none'}|{score_rows}|{last_fixture or 0}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]
