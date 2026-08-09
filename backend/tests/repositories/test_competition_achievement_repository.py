from datetime import datetime, timezone

import pytest

from sfa.domain.scoring.entities import CompetitionAchievement
from sfa.infrastructure.repositories.competition_achievement_repository import (
    CompetitionAchievementRepository,
)


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class FakeSession:
    def __init__(self, results):
        self._results = list(results)
        self.statements = []
        self.flushes = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self._results.pop(0)

    async def flush(self):
        self.flushes += 1


@pytest.mark.anyio
async def test_get_domestic_league_leaders_maps_latest_standing_rows():
    session = FakeSession([
        FakeResult(rows=[{
            "competition_id": 39,
            "competition_name": "Premier League",
            "team_id": 10,
            "season": "2025",
            "matchday": 38,
            "team_count": 20,
            "regular_fixture_count": 380,
            "pending_fixture_count": 0,
        }]),
    ])

    result = await CompetitionAchievementRepository(
        session
    ).get_domestic_league_leaders("2025", ["Premier League"])

    assert len(result) == 1
    assert result[0].competition_id == 39
    assert result[0].team_id == 10
    assert result[0].matchday == 38
    assert result[0].team_count == 20
    assert result[0].regular_fixture_count == 380
    assert result[0].pending_fixture_count == 0
    statement = str(session.statements[0])
    assert "standing_snapshots" in statement
    assert "position" in statement


@pytest.mark.anyio
async def test_replace_achievement_for_phase_deletes_stale_team_before_upsert():
    session = FakeSession([FakeResult(), FakeResult(scalar=44)])
    achievement = CompetitionAchievement(
        id=None,
        competition_id=39,
        team_id=10,
        season="2025",
        phase="champion",
        bonus_points=7000,
        weight=1.0,
        created_at=datetime.now(timezone.utc),
    )

    achievement_id = await CompetitionAchievementRepository(
        session
    ).replace_achievement_for_phase(achievement)

    assert achievement_id == 44
    assert len(session.statements) == 2
    delete_statement = str(session.statements[0])
    assert "DELETE FROM competition_achievements" in delete_statement
    assert "team_id !=" in delete_statement
    assert session.flushes == 2


@pytest.mark.anyio
async def test_clear_achievement_bonuses_deletes_details_and_resets_score_totals():
    session = FakeSession([FakeResult(), FakeResult()])

    await CompetitionAchievementRepository(session).clear_achievement_bonuses(
        competition_id=39,
        season="2025",
        rules_version_id=4,
    )

    assert len(session.statements) == 2
    assert "DELETE FROM player_achievement_bonuses" in str(session.statements[0])
    update_statement = str(session.statements[1])
    assert "UPDATE sfa_season_scores" in update_statement
    assert "achievement_bonus_pts" in update_statement
    assert session.flushes == 1
