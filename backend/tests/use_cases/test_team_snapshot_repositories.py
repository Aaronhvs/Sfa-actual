from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sfa.domain.scoring_ports import FixtureTeamStrengthDTO
from sfa.infrastructure.models.enums import Position
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.repositories.competition_achievement_repository import (
    CompetitionAchievementRepository,
)
from sfa.infrastructure.repositories.player_event_score_repository import (
    PlayerEventScoreRepository,
)
from sfa.infrastructure.repositories.sfa_score_repository import SFAScoreRepository
from sfa.infrastructure.repositories.team_strength_repository import (
    TeamStrengthRepository,
)


class FakeResult:
    def __init__(
        self,
        *,
        rows: list[object] | None = None,
        scalar: object | None = None,
    ) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def all(self) -> list[object]:
        return self._rows

    def fetchall(self) -> list[object]:
        return self._rows

    def mappings(self) -> FakeResult:
        return self

    def scalar_one_or_none(self) -> object | None:
        return self._scalar


class FakeSession:
    def __init__(self, results: list[FakeResult]) -> None:
        self._results = results
        self.statements: list[object] = []

    async def execute(self, statement: object, params: object | None = None) -> FakeResult:
        self.statements.append(statement)
        return self._results.pop(0)

    async def flush(self) -> None:
        return None


def test_player_model_accepts_null_legacy_team_during_expand() -> None:
    player = Player(
        external_id=133609,
        name="Pedri",
        position=Position.MC,
    )

    assert Player.__table__.c.team_id.nullable is True
    assert player.team_id is None


@pytest.mark.anyio
async def test_elo_replay_rejects_fixture_without_official_score() -> None:
    unresolved = SimpleNamespace(
        fixture_id=10,
        home_team_id=1,
        away_team_id=2,
        played_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        competition_id=3,
        home_goals=None,
        away_goals=0,
        season="2025",
        score_source=None,
    )
    session = FakeSession([FakeResult(rows=[unresolved])])

    with pytest.raises(
        ValueError,
        match="Missing official score or provenance for fixture_ids: 10",
    ):
        await TeamStrengthRepository(session).get_fixtures_for_elo_recalc(
            "2025",
            [3],
        )

    sql = str(session.statements[0])
    assert "fixtures.home_goals" in sql
    assert "fixtures.away_goals" in sql
    assert "player_stats" not in sql


@pytest.mark.anyio
async def test_player_rank_in_team_filters_season_score_snapshot() -> None:
    session = FakeSession([FakeResult(scalar=1)])

    rank = await CompetitionAchievementRepository(session).get_player_rank_in_team(
        player_id=7,
        team_id=2,
        competition_id=3,
        season="2025",
        rules_version_id=4,
    )

    assert rank == 1
    sql = str(session.statements[0])
    assert "sfa_season_scores.team_id" in sql
    assert "players.team_id" not in sql


@pytest.mark.anyio
async def test_ranking_joins_team_from_season_score_snapshot() -> None:
    session = FakeSession([FakeResult()])

    rows = await SFAScoreRepository(session).get_ranking(
        season="2025",
        competition_id=3,
        rules_version_id=4,
    )

    assert rows == []
    sql = str(session.statements[0])
    assert "players.team_id" not in sql
    assert "team_id" in sql


@pytest.mark.anyio
async def test_bulk_rebuild_uses_team_with_most_appearance_minutes() -> None:
    session = FakeSession([FakeResult()])

    updated = await PlayerEventScoreRepository(session).bulk_rebuild_season_scores(
        rules_version_id=4,
        season="2025",
        competition_id=3,
    )

    assert updated == 0
    sql = str(session.statements[0])
    assert "team_minutes AS" in sql
    assert "SUM(ps.minutes) DESC" in sql
    assert "JOIN players" not in sql


@pytest.mark.anyio
async def test_event_context_prefers_fixture_elo_snapshot_before_current_strength() -> None:
    session = FakeSession([FakeResult(rows=[])])

    rows = await PlayerEventScoreRepository(session).get_events_for_recalc(
        season="2025",
        competition_id=3,
        match_id=None,
        player_id=None,
    )

    assert rows == []
    sql = str(session.statements[0])
    assert "fixture_team_strengths AS elo_home" in sql
    assert "fixture_team_strengths AS elo_away" in sql
    assert "elo_home.pre_match_strength" in sql
    assert "elo_away.pre_match_strength" in sql
    assert " LEFT OUTER JOIN team_strengths " not in sql


@pytest.mark.anyio
async def test_event_context_rejects_missing_temporal_elo_snapshot() -> None:
    event_row = SimpleNamespace(
        fixture_id=99,
        home_team_strength=71.43,
        away_team_strength=None,
    )
    session = FakeSession([FakeResult(rows=[event_row])])

    with pytest.raises(ValueError, match="Missing temporal ELO snapshot for fixture_ids: 99"):
        await PlayerEventScoreRepository(session).get_events_for_recalc(
            season="2025",
            competition_id=3,
            match_id=99,
            player_id=None,
        )


@pytest.mark.anyio
async def test_replace_fixture_team_strengths_replaces_scope_and_bulk_inserts() -> None:
    session = FakeSession([FakeResult(), FakeResult()])
    snapshots = [
        FixtureTeamStrengthDTO(
            10, 1, "2025", 3, "club", 1900.0, 1910.0, 71.43, 72.86,
            "club_elo_v2", "clubelo",
        ),
        FixtureTeamStrengthDTO(
            10, 2, "2025", 3, "club", 1650.0, 1640.0, 35.71, 34.29,
            "club_elo_v2", "clubelo",
        ),
    ]

    await TeamStrengthRepository(session).replace_fixture_team_strengths(
        "2025",
        "club",
        [3],
        snapshots,
    )

    assert len(session.statements) == 2
    assert "DELETE FROM fixture_team_strengths" in str(session.statements[0])
    insert_sql = str(session.statements[1])
    assert "INSERT INTO fixture_team_strengths" in insert_sql
    assert "ON CONFLICT (fixture_id, team_id) DO UPDATE" in insert_sql
