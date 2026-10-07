from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, distinct, func, select, true, tuple_, union, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from sfa.domain.team_ranking_ports import (
    TeamRankingDataDTO,
    TeamRankingEloDTO,
    TeamRankingInputDTO,
    TeamRankingPlayerDTO,
    TeamRankingRepositoryProtocol,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion
from sfa.infrastructure.models.team_strengths.models import TeamStrength
from sfa.infrastructure.models.teams.models import Team

ELO_SOURCES = ("clubelo_seed", "elo_v1", "club_elo_v2", "national_elo_seed", "national_elo_v1")
DOMESTIC_LEAGUE_NAMES = ("La Liga", "Premier League", "Bundesliga", "Serie A", "Ligue 1")


def _database_participant_kind(participant_kind: str) -> str:
    return "national_team" if participant_kind == "national" else participant_kind


def _population(season: str, participant_kind: str):
    participant_kind = _database_participant_kind(participant_kind)
    def side(column):
        return (
            select(column.label("team_id"), Fixture.competition_id)
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(Fixture.season == season, Competition.participant_kind == participant_kind)
        )

    strengths = (
        select(TeamStrength.team_id, TeamStrength.competition_id)
        .join(Competition, Competition.id == TeamStrength.competition_id)
        .where(TeamStrength.season == season, Competition.participant_kind == participant_kind)
    )
    return union(side(Fixture.home_team_id), side(Fixture.away_team_id), strengths).cte("population")


def _primary_domestic_leagues(season: str, participant_kind: str):
    def side(column):
        return (
            select(column.label("team_id"), Fixture.id.label("fixture_id"), Fixture.competition_id, Fixture.played_at)
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(Fixture.season == season,
                   Competition.participant_kind == _database_participant_kind(participant_kind),
                   Competition.name.in_(DOMESTIC_LEAGUE_NAMES))
        )

    sides = union_all(side(Fixture.home_team_id), side(Fixture.away_team_id)).cte("domestic_participation")
    grouped = (
        select(sides.c.team_id, sides.c.competition_id, Competition.name,
               func.count(distinct(sides.c.fixture_id)).label("fixtures"),
               func.max(sides.c.played_at).label("last_fixture"))
        .join(Competition, Competition.id == sides.c.competition_id)
        .group_by(sides.c.team_id, sides.c.competition_id, Competition.name)
        .cte("domestic_leagues")
    )
    return select(
        grouped,
        func.row_number().over(
            partition_by=grouped.c.team_id,
            order_by=(grouped.c.fixtures.desc(), grouped.c.last_fixture.desc(), grouped.c.competition_id.asc()),
        ).label("preference"),
    ).cte("primary_domestic_leagues")


def _teams_statement(season: str, participant_kind: str):
    population = _population(season, participant_kind)
    primary = _primary_domestic_leagues(season, participant_kind)
    catalog = aliased(Competition)
    return (
        select(Team.id, Team.name, Team.external_id,
               func.coalesce(primary.c.competition_id, Team.competition_id).label("competition_id"),
               func.coalesce(primary.c.name, catalog.name).label("competition"),
               func.array_agg(func.distinct(population.c.competition_id)).label("competition_ids"))
        .join(population, population.c.team_id == Team.id)
        .join(catalog, catalog.id == Team.competition_id)
        .outerjoin(primary, (primary.c.team_id == Team.id) & (primary.c.preference == 1))
        .group_by(Team.id, catalog.name, primary.c.competition_id, primary.c.name)
    )


def _recent_appearances(season, prior_season, participant_kind, as_of, recent_matches):
    participant_kind = _database_participant_kind(participant_kind)
    def side(column):
        return (
            select(
                column.label("team_id"), Fixture.id.label("fixture_id"), Fixture.season,
                Fixture.played_at,
            )
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(
                Fixture.season.in_((season, prior_season)),
                Competition.participant_kind == participant_kind,
                Fixture.status.in_(("FT", "AET", "PEN")), Fixture.played_at <= as_of,
            )
        )

    sides = union_all(side(Fixture.home_team_id), side(Fixture.away_team_id)).cte("fixture_sides")
    ordered = select(
        sides,
        func.row_number().over(
            partition_by=(sides.c.team_id, sides.c.season),
            order_by=(sides.c.played_at.desc(), sides.c.fixture_id.desc()),
        ).label("recency"),
    ).cte("ordered_fixtures")
    population = _population(season, participant_kind)
    return (
        select(PlayerStats.player_id, PlayerStats.fixture_id, PlayerStats.team_id, PlayerStats.season,
               PlayerStats.minutes, ordered.c.played_at)
        .join(ordered, (ordered.c.fixture_id == PlayerStats.fixture_id) & (ordered.c.team_id == PlayerStats.team_id))
        .where(
            ordered.c.recency <= recent_matches, PlayerStats.season == ordered.c.season,
            PlayerStats.minutes > 0, PlayerStats.team_id.in_(select(population.c.team_id)),
        )
        .cte("verified_appearances")
        .prefix_with("MATERIALIZED", dialect="postgresql")
    )


def _version_statement(appearances, season):
    # PostgreSQL otherwise underestimates the window join and repeatedly scans scores by season.
    seasons = select(appearances.c.season).distinct().cte("observed_seasons")
    seasons = seasons.prefix_with("MATERIALIZED", dialect="postgresql")
    candidates = (
        select(PlayerEventScore.player_id, PlayerEventScore.fixture_id,
               PlayerEventScore.season, PlayerEventScore.rules_version_id)
        .where(PlayerEventScore.action_type == "stats",
               PlayerEventScore.season.in_(select(seasons.c.season)))
        .cte("version_candidates")
        .prefix_with("MATERIALIZED", dialect="postgresql")
    )
    # Set intersection remains bounded under generic prepared plans; an underestimated semijoin may not.
    covered = select(
        candidates.c.fixture_id, candidates.c.player_id, candidates.c.season, candidates.c.rules_version_id,
    ).intersect(
        select(appearances.c.fixture_id, appearances.c.player_id, appearances.c.season, ScoringRulesVersion.id)
        .select_from(appearances).join(ScoringRulesVersion, true()),
    ).cte("covered_versions")
    return (
        select(covered.c.rules_version_id)
        .join(ScoringRulesVersion, ScoringRulesVersion.id == covered.c.rules_version_id)
        .group_by(covered.c.rules_version_id, ScoringRulesVersion.is_active)
        .order_by(
            func.count(distinct(tuple_(covered.c.fixture_id, covered.c.player_id)))
            .filter(covered.c.season == season).desc(),
            func.count(distinct(tuple_(covered.c.fixture_id, covered.c.player_id))).desc(),
            ScoringRulesVersion.is_active.desc(), covered.c.rules_version_id.desc(),
        ).limit(1)
    )


def _players_statement(appearances, rules_version_id):
    seasons = select(appearances.c.season).distinct().cte("observed_seasons")
    seasons = seasons.prefix_with("MATERIALIZED", dialect="postgresql")
    scores = (
        select(
            PlayerEventScore.player_id, PlayerEventScore.fixture_id, PlayerEventScore.season,
            func.sum(PlayerEventScore.final_points).label("points"),
            func.max(case((PlayerEventScore.action_type == "stats", 1), else_=0)).label("has_stats"),
        )
        .where(PlayerEventScore.rules_version_id == rules_version_id)
        .where(PlayerEventScore.season.in_(select(seasons.c.season)))
        .group_by(PlayerEventScore.player_id, PlayerEventScore.fixture_id, PlayerEventScore.season)
        .cte("individual_scores")
        .prefix_with("MATERIALIZED", dialect="postgresql")
    )
    covered = scores.c.has_stats == 1
    return (
        select(
            appearances.c.team_id, appearances.c.player_id, appearances.c.season, Player.position,
            func.count().label("observed_appearances"),
            func.sum(case((covered, 1), else_=0)).label("scored_appearances"),
            func.sum(case((covered, appearances.c.minutes), else_=0)).label("scored_minutes"),
            func.sum(case((covered, scores.c.points), else_=None)).label("individual_points"),
            func.max(case((covered, appearances.c.played_at), else_=None)).label("data_cutoff"),
        )
        .join(Player, Player.id == appearances.c.player_id)
        .outerjoin(scores, (scores.c.fixture_id == appearances.c.fixture_id)
                   & (scores.c.player_id == appearances.c.player_id) & (scores.c.season == appearances.c.season))
        .group_by(appearances.c.team_id, appearances.c.player_id, appearances.c.season, Player.position)
    )


class TeamRankingRepository(TeamRankingRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_season(self, participant_kind: str) -> str | None:
        statement = (
            select(Fixture.season).join(Competition, Competition.id == Fixture.competition_id)
            .where(Competition.participant_kind == _database_participant_kind(participant_kind))
            .order_by(Fixture.season.desc()).limit(1)
        )
        return await self._session.scalar(statement)

    async def get_ranking_data(
        self, season: str, prior_season: str, participant_kind: str,
        as_of: datetime, recent_matches: int,
    ) -> TeamRankingDataDTO:
        participant_kind = _database_participant_kind(participant_kind)
        statement = _teams_statement(season, participant_kind)
        rows = (await self._session.execute(statement)).mappings().all()
        teams = tuple(TeamRankingInputDTO(
            r["id"], r["name"], r["external_id"], r["competition_id"], r["competition"],
            tuple(sorted(r["competition_ids"])),
        ) for r in rows)
        if not teams:
            return TeamRankingDataDTO()
        ids = [team.id for team in teams]
        elo_rows = (
            select(TeamStrength.team_id, TeamStrength.season, TeamStrength.elo_raw, TeamStrength.source,
                   func.row_number().over(
                       partition_by=(TeamStrength.team_id, TeamStrength.season),
                       order_by=TeamStrength.competition_id.asc(),
                   ).label("selection"))
            .join(Competition, Competition.id == TeamStrength.competition_id)
            .where(TeamStrength.team_id.in_(ids), TeamStrength.season.in_((season, prior_season)),
                   TeamStrength.elo_raw.is_not(None), TeamStrength.source.in_(ELO_SOURCES),
                   Competition.participant_kind == participant_kind)
            .cte("elo_rows")
        )
        rows = (await self._session.execute(select(elo_rows).where(elo_rows.c.selection == 1))).mappings().all()
        elos = tuple(TeamRankingEloDTO(r["team_id"], r["season"], float(r["elo_raw"]), r["source"]) for r in rows)
        appearances = _recent_appearances(season, prior_season, participant_kind, as_of, recent_matches)
        rules_version_id = await self._session.scalar(_version_statement(appearances, season))
        rows = (await self._session.execute(_players_statement(appearances, rules_version_id))).mappings().all()
        players = tuple(TeamRankingPlayerDTO(
            team_id=r["team_id"], player_id=r["player_id"], season=r["season"],
            position=getattr(r["position"], "value", r["position"]),
            observed_appearances=int(r["observed_appearances"]), scored_appearances=int(r["scored_appearances"]),
            scored_minutes=int(r["scored_minutes"]),
            individual_points=float(r["individual_points"]) if r["individual_points"] is not None else None,
            data_cutoff=r["data_cutoff"],
        ) for r in rows)
        return TeamRankingDataDTO(teams, elos, players, rules_version_id)
