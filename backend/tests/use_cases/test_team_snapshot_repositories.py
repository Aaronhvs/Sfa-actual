from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

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
async def test_elo_excludes_fixture_with_unresolved_team_snapshot(caplog) -> None:
    unresolved = SimpleNamespace(
        fixture_id=10,
        home_team_id=1,
        away_team_id=2,
        played_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        competition_id=3,
        home_goals=0,
        away_goals=0,
        season="2025",
        unresolved_players=1,
    )
    session = FakeSession([FakeResult(rows=[unresolved])])

    rows = await TeamStrengthRepository(session).get_fixtures_for_elo_recalc(
        "2025",
        [3],
    )

    assert rows == []
    assert "Excluding fixture_id=10 from ELO" in caplog.text
    sql = str(session.statements[0])
    assert "player_stats.team_id" in sql
    assert "players.team_id = fixtures.home_team_id" in sql
    assert "players.team_id = fixtures.away_team_id" in sql


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
