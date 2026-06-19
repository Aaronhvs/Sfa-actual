import collections
import datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import (
    FixtureActionBreakdown,
    PlayerEventDTO,
    PlayerEventRepositoryProtocol,
    PlayerFixtureDTO,
    PlayerSeasonStatsDTO,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.teams.models import Team


class PlayerEventRepository(PlayerEventRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _effective_rules_version_id(
        self,
        season: str | None,
        rules_version_id: int | None = None,
    ) -> int | None:
        if rules_version_id is not None:
            return rules_version_id

        active_id = await self._session.scalar(
            select(ScoringRulesVersion.id)
            .where(ScoringRulesVersion.is_active.is_(True))
            .limit(1)
        )
        if season is None:
            return active_id

        if active_id is not None:
            active_rows = await self._session.scalar(
                select(func.count())
                .select_from(SFASeasonScore)
                .where(
                    SFASeasonScore.season == season,
                    SFASeasonScore.rules_version_id == active_id,
                )
            )
            if active_rows and active_rows > 0:
                return int(active_id)

        latest_for_season = await self._session.scalar(
            select(func.max(SFASeasonScore.rules_version_id)).where(
                SFASeasonScore.season == season,
                SFASeasonScore.rules_version_id.is_not(None),
            )
        )
        if latest_for_season is not None:
            return int(latest_for_season)

        return active_id

    async def get_events_by_player(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
        rules_version_id: int | None = None,
    ) -> list[PlayerEventDTO]:
        home_alias = Team.__table__.alias("ht")
        away_alias = Team.__table__.alias("at")
        historical_scores = season is None and rules_version_id is None
        if historical_scores:
            score_ranked = (
                select(
                    PlayerEventScore.event_id,
                    PlayerEventScore.m1,
                    PlayerEventScore.m2,
                    PlayerEventScore.m3,
                    PlayerEventScore.m4,
                    PlayerEventScore.mvisit,
                    PlayerEventScore.final_points,
                    func.row_number().over(
                        partition_by=PlayerEventScore.event_id,
                        order_by=PlayerEventScore.rules_version_id.desc(),
                    ).label("rn"),
                )
                .subquery()
            )
            score_join = and_(
                score_ranked.c.event_id == PlayerEvent.id,
                score_ranked.c.rn == 1,
            )
            score_m1 = score_ranked.c.m1
            score_m2 = score_ranked.c.m2
            score_m3 = score_ranked.c.m3
            score_m4 = score_ranked.c.m4
            score_mvisit = score_ranked.c.mvisit
            score_final_points = score_ranked.c.final_points
            score_source = score_ranked
        else:
            effective_rules_version_id = await self._effective_rules_version_id(
                season, rules_version_id,
            )
            score_join = and_(
                PlayerEventScore.event_id == PlayerEvent.id,
                PlayerEventScore.rules_version_id == effective_rules_version_id,
            )
            score_m1 = PlayerEventScore.m1
            score_m2 = PlayerEventScore.m2
            score_m3 = PlayerEventScore.m3
            score_m4 = PlayerEventScore.m4
            score_mvisit = PlayerEventScore.mvisit
            score_final_points = PlayerEventScore.final_points
            score_source = PlayerEventScore

        stmt = (
            select(
                PlayerEvent.id,
                Competition.name.label("competition"),
                Fixture.stage,
                Fixture.id.label("fixture_id"),
                home_alias.c.name.label("home_team"),
                away_alias.c.name.label("away_team"),
                Fixture.played_at,
                PlayerEvent.minute,
                PlayerEvent.event_type,
                PlayerEvent.score_before,
                PlayerEvent.score_diff,
                func.coalesce(score_m1, PlayerEvent.m1).label("m1"),
                func.coalesce(score_m2, PlayerEvent.m2).label("m2"),
                func.coalesce(score_m3, PlayerEvent.m3).label("m3"),
                func.coalesce(score_m4, PlayerEvent.m4).label("m4"),
                func.coalesce(score_mvisit, PlayerEvent.mvisit).label("mvisit"),
                func.coalesce(score_final_points, PlayerEvent.pts).label("pts"),
            )
            .join(Fixture, PlayerEvent.fixture_id == Fixture.id)
            .join(Competition, Fixture.competition_id == Competition.id)
            .join(home_alias, Fixture.home_team_id == home_alias.c.id)
            .join(away_alias, Fixture.away_team_id == away_alias.c.id)
            .outerjoin(
                score_source,
                score_join,
            )
            .where(PlayerEvent.player_id == player_id)
            .order_by(Fixture.played_at.desc(), PlayerEvent.minute.asc())
        )
        if season is not None:
            stmt = stmt.where(Fixture.season == season)
        if competition_id is not None:
            stmt = stmt.where(Fixture.competition_id == competition_id)

        rows = (await self._session.execute(stmt)).mappings().all()
        return [PlayerEventDTO(**dict(row)) for row in rows]

    async def get_fixtures_by_player(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
        competition_name: str | None = None,
        rival: str | None = None,
        date: datetime.date | None = None,
        rules_version_id: int | None = None,
    ) -> list[PlayerFixtureDTO]:
        home_alias = Team.__table__.alias("ht")
        away_alias = Team.__table__.alias("at")
        player_stats_team_alias = Team.__table__.alias("pst")
        player_event_team_alias = Team.__table__.alias("pet")
        season_score_team_alias = Team.__table__.alias("sst")
        season_score_team = (
            select(
                SFASeasonScore.player_id,
                SFASeasonScore.season,
                SFASeasonScore.competition_id,
                SFASeasonScore.team_id,
                func.row_number().over(
                    partition_by=(
                        SFASeasonScore.player_id,
                        SFASeasonScore.season,
                        SFASeasonScore.competition_id,
                    ),
                    order_by=SFASeasonScore.rules_version_id.desc(),
                ).label("rn"),
            )
            .where(SFASeasonScore.player_id == player_id)
            .where(SFASeasonScore.team_id.is_not(None))
            .subquery()
        )
        historical_scores = season is None and rules_version_id is None
        if historical_scores:
            score_ranked = (
                select(
                    PlayerEventScore.event_id,
                    PlayerEventScore.final_points,
                    func.row_number().over(
                        partition_by=PlayerEventScore.event_id,
                        order_by=PlayerEventScore.rules_version_id.desc(),
                    ).label("rn"),
                )
                .subquery()
            )
            score_join = and_(
                score_ranked.c.event_id == PlayerEvent.id,
                score_ranked.c.rn == 1,
            )
            score_final_points = score_ranked.c.final_points
            score_source = score_ranked
        else:
            effective_rules_version_id = await self._effective_rules_version_id(
                season, rules_version_id,
            )
            score_join = and_(
                PlayerEventScore.event_id == PlayerEvent.id,
                PlayerEventScore.rules_version_id == effective_rules_version_id,
            )
            score_final_points = PlayerEventScore.final_points
            score_source = PlayerEventScore

        stmt = (
            select(
                Fixture.id.label("fixture_id"),
                Competition.name.label("competition"),
                Fixture.stage,
                home_alias.c.name.label("home_team"),
                away_alias.c.name.label("away_team"),
                home_alias.c.external_id.label("home_team_ext_id"),
                away_alias.c.external_id.label("away_team_ext_id"),
                func.coalesce(
                    func.max(player_stats_team_alias.c.name),
                    func.max(player_event_team_alias.c.name),
                    func.max(season_score_team_alias.c.name),
                    func.max(
                        case(
                            (PlayerEvent.is_away.is_(True), away_alias.c.name),
                            (PlayerEvent.is_away.is_(False), home_alias.c.name),
                            else_=None,
                        )
                    ),
                ).label("player_team"),
                func.coalesce(
                    func.max(player_stats_team_alias.c.external_id),
                    func.max(player_event_team_alias.c.external_id),
                    func.max(season_score_team_alias.c.external_id),
                    func.max(
                        case(
                            (PlayerEvent.is_away.is_(True), away_alias.c.external_id),
                            (PlayerEvent.is_away.is_(False), home_alias.c.external_id),
                            else_=None,
                        )
                    ),
                ).label("player_team_ext_id"),
                Fixture.played_at,
                func.coalesce(func.sum(score_final_points), 0).label("sfa_pts"),
                func.count(PlayerEvent.id).label("events_count"),
                func.coalesce(func.max(PlayerStats.minutes), 0).label("minutes"),
                func.coalesce(func.max(PlayerStats.shots_total), 0).label("shots_total"),
                func.coalesce(func.max(PlayerStats.shots_on), 0).label("shots_on"),
                func.coalesce(func.max(PlayerStats.passes_total), 0).label("passes_total"),
                func.coalesce(
                    func.max(func.round(PlayerStats.passes_total * PlayerStats.passes_accuracy / 100)),
                    0,
                ).label("passes_accurate"),
                func.coalesce(func.max(PlayerStats.passes_key), 0).label("passes_key"),
                func.coalesce(func.max(PlayerStats.dribbles_won), 0).label("dribbles_won"),
                func.coalesce(func.max(PlayerStats.duels_won), 0).label("duels_won"),
                func.coalesce(func.max(PlayerStats.tackles_won), 0).label("tackles_won"),
                func.coalesce(func.max(PlayerStats.interceptions), 0).label("interceptions"),
                func.coalesce(func.max(PlayerStats.blocks), 0).label("blocks"),
                func.coalesce(func.max(PlayerStats.fouls_drawn), 0).label("fouls_drawn"),
                func.max(PlayerStats.rating).label("rating"),
                Fixture.external_id.label("fixture_external_id"),
                Fixture.competition_id.label("fixture_competition_id"),
            )
            .join(Fixture, PlayerEvent.fixture_id == Fixture.id)
            .join(Competition, Fixture.competition_id == Competition.id)
            .join(home_alias, Fixture.home_team_id == home_alias.c.id)
            .join(away_alias, Fixture.away_team_id == away_alias.c.id)
            .outerjoin(
                score_source,
                score_join,
            )
            .outerjoin(
                PlayerStats,
                and_(
                    PlayerStats.player_id == player_id,
                    PlayerStats.fixture_id == Fixture.id,
                ),
            )
            .outerjoin(player_stats_team_alias, PlayerStats.team_id == player_stats_team_alias.c.id)
            .outerjoin(player_event_team_alias, PlayerEvent.team_id == player_event_team_alias.c.id)
            .outerjoin(
                season_score_team,
                and_(
                    season_score_team.c.player_id == player_id,
                    season_score_team.c.season == Fixture.season,
                    season_score_team.c.competition_id == Fixture.competition_id,
                    season_score_team.c.rn == 1,
                ),
            )
            .outerjoin(season_score_team_alias, season_score_team.c.team_id == season_score_team_alias.c.id)
            .where(PlayerEvent.player_id == player_id)
            .group_by(
                Fixture.id,
                Fixture.external_id,
                Fixture.competition_id,
                Competition.name,
                Fixture.stage,
                home_alias.c.name,
                away_alias.c.name,
                home_alias.c.external_id,
                away_alias.c.external_id,
                Fixture.played_at,
            )
            .order_by(Fixture.played_at.desc())
        )
        if season is not None:
            stmt = stmt.where(Fixture.season == season)
        if competition_id is not None:
            stmt = stmt.where(Fixture.competition_id == competition_id)
        if competition_name is not None:
            stmt = stmt.where(Competition.name.ilike(f"%{competition_name}%"))
        if rival is not None:
            stmt = stmt.where(
                or_(
                    home_alias.c.name.ilike(f"%{rival}%"),
                    away_alias.c.name.ilike(f"%{rival}%"),
                )
            )
        if date is not None:
            stmt = stmt.where(func.date(Fixture.played_at) == date)

        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            PlayerFixtureDTO(
                fixture_id=row["fixture_id"],
                competition=row["competition"],
                stage=row["stage"],
                home_team=row["home_team"],
                away_team=row["away_team"],
                played_at=row["played_at"],
                sfa_pts=row["sfa_pts"],
                events_count=row["events_count"],
                player_team=row["player_team"],
                minutes=row["minutes"],
                shots_total=row["shots_total"],
                shots_on=row["shots_on"],
                passes_total=row["passes_total"],
                passes_accurate=row["passes_accurate"],
                passes_key=row["passes_key"],
                dribbles_won=row["dribbles_won"],
                duels_won=row["duels_won"],
                tackles_won=row["tackles_won"],
                interceptions=row["interceptions"],
                blocks=row["blocks"],
                fouls_drawn=row["fouls_drawn"],
                home_team_logo=f"https://media.api-sports.io/football/teams/{row['home_team_ext_id']}.png"
                if row["home_team_ext_id"] else None,
                away_team_logo=f"https://media.api-sports.io/football/teams/{row['away_team_ext_id']}.png"
                if row["away_team_ext_id"] else None,
                player_team_logo=f"https://media.api-sports.io/football/teams/{row['player_team_ext_id']}.png"
                if row["player_team_ext_id"] else None,
                rating=float(row["rating"]) if row["rating"] is not None else None,
                fixture_external_id=row["fixture_external_id"],
                competition_id=row["fixture_competition_id"],
            )
            for row in rows
        ]

    async def get_player_season_stats(
        self,
        player_id: int,
        competition_id: int | None,
        season: str | None,
    ) -> PlayerSeasonStatsDTO | None:
        weighted_pass_accuracy = func.coalesce(
            func.sum(PlayerStats.passes_accuracy * PlayerStats.passes_total)
            / func.nullif(func.sum(PlayerStats.passes_total), 0),
            0,
        )
        stmt = (
            select(
                func.count().label("matches"),
                func.coalesce(func.sum(PlayerStats.minutes), 0).label("minutes"),
                func.coalesce(func.sum(PlayerStats.goals), 0).label("goals"),
                func.coalesce(func.sum(PlayerStats.assists), 0).label("assists"),
                func.coalesce(func.sum(PlayerStats.shots_total), 0).label("shots_total"),
                func.coalesce(func.sum(PlayerStats.shots_on), 0).label("shots_on"),
                func.coalesce(func.sum(PlayerStats.passes_total), 0).label("passes_total"),
                weighted_pass_accuracy.label("passes_accuracy_avg"),
                func.coalesce(func.sum(PlayerStats.passes_key), 0).label("passes_key"),
                func.coalesce(func.sum(PlayerStats.dribbles_won), 0).label("dribbles_won"),
                func.coalesce(func.sum(PlayerStats.dribbles_attempts), 0).label("dribbles_attempts"),
                func.coalesce(func.sum(PlayerStats.dribbles_past), 0).label("dribbles_past"),
                func.coalesce(func.sum(PlayerStats.duels_won), 0).label("duels_won"),
                func.coalesce(func.sum(PlayerStats.duels_total), 0).label("duels_total"),
                func.coalesce(func.sum(PlayerStats.tackles_won), 0).label("tackles_won"),
                func.coalesce(func.sum(PlayerStats.interceptions), 0).label("interceptions"),
                func.coalesce(func.sum(PlayerStats.blocks), 0).label("blocks"),
                func.coalesce(func.sum(PlayerStats.fouls_drawn), 0).label("fouls_drawn"),
                func.coalesce(func.sum(PlayerStats.fouls_committed), 0).label("fouls_committed"),
                func.coalesce(func.sum(PlayerStats.cards_yellow), 0).label("cards_yellow"),
                func.coalesce(func.sum(PlayerStats.cards_red), 0).label("cards_red"),
                func.coalesce(func.sum(PlayerStats.penalty_won), 0).label("penalty_won"),
                func.coalesce(func.sum(PlayerStats.saves), 0).label("saves"),
                func.coalesce(func.sum(PlayerStats.goals_conceded), 0).label("goals_conceded"),
                func.avg(PlayerStats.rating).label("rating_avg"),
            )
            .join(Fixture, PlayerStats.fixture_id == Fixture.id)
            .where(PlayerStats.player_id == player_id)
        )
        if competition_id is not None:
            stmt = stmt.where(Fixture.competition_id == competition_id)
        if season is not None:
            stmt = stmt.where(PlayerStats.season == season)
        row = (await self._session.execute(stmt)).mappings().one_or_none()
        if row is None or row["matches"] == 0:
            return None

        dribbles_won = int(row["dribbles_won"])
        dribbles_attempts = int(row["dribbles_attempts"])
        duels_won = int(row["duels_won"])
        duels_total = int(row["duels_total"])

        return PlayerSeasonStatsDTO(
            player_id=player_id,
            competition_id=competition_id,
            season=season or "all",
            matches=int(row["matches"]),
            minutes=int(row["minutes"]),
            goals=int(row["goals"]),
            assists=int(row["assists"]),
            shots_total=int(row["shots_total"]),
            shots_on=int(row["shots_on"]),
            passes_total=int(row["passes_total"]),
            passes_accuracy_avg=round(float(row["passes_accuracy_avg"]), 1),
            passes_key=int(row["passes_key"]),
            dribbles_won=dribbles_won,
            dribbles_attempts=dribbles_attempts,
            dribbles_past=int(row["dribbles_past"]),
            duels_won=duels_won,
            duels_total=duels_total,
            tackles_won=int(row["tackles_won"]),
            interceptions=int(row["interceptions"]),
            blocks=int(row["blocks"]),
            fouls_drawn=int(row["fouls_drawn"]),
            fouls_committed=int(row["fouls_committed"]),
            cards_yellow=int(row["cards_yellow"]),
            cards_red=int(row["cards_red"]),
            penalty_won=int(row["penalty_won"]),
            saves=int(row["saves"]),
            goals_conceded=int(row["goals_conceded"]),
            rating_avg=round(float(row["rating_avg"]), 2) if row["rating_avg"] is not None else None,
            dribble_success_rate=round(dribbles_won / dribbles_attempts, 3) if dribbles_attempts > 0 else None,
            duel_win_rate=round(duels_won / duels_total, 3) if duels_total > 0 else None,
        )

    async def get_fixture_breakdown_by_player(
        self,
        player_id: int,
        fixture_ids: list[int],
        season: str | None = None,
        rules_version_id: int | None = None,
    ) -> dict[int, dict[str, FixtureActionBreakdown]]:
        if not fixture_ids:
            return {}
        historical_scores = season is None and rules_version_id is None
        if historical_scores:
            score_ranked = (
                select(
                    PlayerEventScore.event_id,
                    PlayerEventScore.final_points,
                    func.row_number().over(
                        partition_by=PlayerEventScore.event_id,
                        order_by=PlayerEventScore.rules_version_id.desc(),
                    ).label("rn"),
                )
                .subquery()
            )
            score_join = and_(
                score_ranked.c.event_id == PlayerEvent.id,
                score_ranked.c.rn == 1,
            )
            score_final_points = score_ranked.c.final_points
            score_source = score_ranked
        else:
            effective_rules_version_id = await self._effective_rules_version_id(
                season, rules_version_id,
            )
            score_join = and_(
                PlayerEventScore.event_id == PlayerEvent.id,
                PlayerEventScore.rules_version_id == effective_rules_version_id,
            )
            score_final_points = PlayerEventScore.final_points
            score_source = PlayerEventScore

        stmt = (
            select(
                PlayerEvent.fixture_id,
                PlayerEvent.event_type,
                func.count().label("count"),
                func.coalesce(func.sum(score_final_points), 0.0).label("pts"),
            )
            .outerjoin(
                score_source,
                score_join,
            )
            .where(PlayerEvent.player_id == player_id)
            .where(PlayerEvent.fixture_id.in_(fixture_ids))
            .group_by(PlayerEvent.fixture_id, PlayerEvent.event_type)
        )

        rows = (await self._session.execute(stmt)).mappings().all()

        result: dict[int, dict[str, FixtureActionBreakdown]] = collections.defaultdict(dict)
        for row in rows:
            event_type_str = row["event_type"].value if hasattr(row["event_type"], "value") else str(row["event_type"])
            result[row["fixture_id"]][event_type_str] = FixtureActionBreakdown(
                count=row["count"],
                pts=float(row["pts"]),
            )
        return dict(result)
