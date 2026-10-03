from sqlalchemy import select

from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.repositories.sfa_score_repository import (
    _latest_verified_team,
    _stable_ranking_order,
    _verified_player_ids,
)


def _sql_for_latest_team(
    season: str,
    scope: AwardPeriodScope | None = None,
    competition_id: int | None = None,
) -> str:
    projection = _latest_verified_team(season, scope, competition_id)
    return str(select(projection)).lower()


def test_latest_team_uses_real_fixture_chronology_and_validates_appearance() -> None:
    sql = _sql_for_latest_team("2025")

    assert "fixtures.played_at desc" in sql
    assert "fixtures.id desc" in sql
    assert "player_stats.id desc" in sql
    assert "player_stats.team_id = fixtures.home_team_id" in sql
    assert "player_stats.team_id = fixtures.away_team_id" in sql
    assert "fixtures.season" in sql
    assert "competitions.participant_kind" in sql


def test_competition_filter_is_applied_without_forcing_club_kind() -> None:
    sql = _sql_for_latest_team("2026", competition_id=350)

    assert "fixtures.competition_id" in sql
    assert "competitions.participant_kind" not in sql


def test_latest_team_can_be_limited_to_the_paginated_players() -> None:
    projection = _latest_verified_team("2025", player_ids=[7, 11])
    sql = str(select(projection)).lower()

    assert "player_stats.player_id in" in sql


def test_verified_player_projection_does_not_resolve_team_context() -> None:
    projection = _verified_player_ids("2025")
    sql = str(select(projection)).lower()

    assert "select distinct player_stats.player_id" in sql
    assert "player_stats.team_id = fixtures.home_team_id" in sql
    assert "player_stats.team_id = fixtures.away_team_id" in sql
    assert "row_number()" not in sql


def test_award_scope_prefers_club_but_tournament_scope_keeps_national_team() -> None:
    award = AwardPeriodScope(
        key="season-2025",
        label="2025/2026",
        kind=ScopeKind.AWARD_PERIOD,
        sources=(ScoreSource("2025", (3,)), ScoreSource("2026", (350,))),
    )
    tournament = AwardPeriodScope(
        key="world-cup-2026",
        label="Mundial 2026",
        kind=ScopeKind.TOURNAMENT,
        sources=(ScoreSource("2026", (350,)),),
    )

    award_sql = _sql_for_latest_team("2025", award)
    tournament_sql = _sql_for_latest_team("2026", tournament)

    assert "competitions.participant_kind" in award_sql
    assert "competitions.participant_kind" not in tournament_sql
    assert "fixtures.competition_id" in tournament_sql


def test_stable_ranking_order_uses_player_id_only_as_final_tiebreaker() -> None:
    order = _stable_ranking_order(Player.id, Player.id)
    sql = [str(item).lower() for item in order]

    assert sql == ["players.id desc", "players.id desc", "players.id asc"]
