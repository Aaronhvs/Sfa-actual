from __future__ import annotations

import pytest

from sfa.infrastructure.repositories.fixture_score_backfill_repository import (
    FixtureScoreBackfillRepository,
)


class FakeResult:
    def __init__(
        self,
        rows: list[dict] | None = None,
        rowcount: int = 0,
    ) -> None:
        self._rows = rows or []
        self.rowcount = rowcount

    def mappings(self) -> FakeResult:
        return self

    def all(self) -> list[dict]:
        return self._rows


class FakeSession:
    def __init__(self, results: list[FakeResult]) -> None:
        self.results = results
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return self.results.pop(0)


@pytest.mark.anyio
async def test_targets_include_only_final_fixtures_with_missing_score_context() -> None:
    session = FakeSession([FakeResult(rows=[{
        "id": 7,
        "external_id": 1007,
        "season": "2025",
        "status": "FT",
        "home_team_external_id": 10,
        "away_team_external_id": 20,
    }])])

    rows = await FixtureScoreBackfillRepository(
        session
    ).get_missing_fixture_score_targets(["2025", "2026"])

    assert rows[0].fixture_id == 7
    assert rows[0].home_team_external_id == 10
    sql = str(session.statements[0])
    assert "fixtures.home_goals IS NULL" in sql
    assert "fixtures.away_goals IS NULL" in sql
    assert "fixtures.score_source IS NULL" in sql
    assert "fixtures.status IN" in sql


@pytest.mark.anyio
async def test_update_fixture_score_sets_authoritative_fields() -> None:
    session = FakeSession([FakeResult(rowcount=1)])

    await FixtureScoreBackfillRepository(session).update_fixture_score(
        fixture_id=7,
        status="PEN",
        home_goals=1,
        away_goals=1,
        score_source="api_football_backfill",
    )

    sql = str(session.statements[0])
    assert "UPDATE fixtures SET" in sql
    assert "home_goals" in sql
    assert "away_goals" in sql
    assert "score_source" in sql


@pytest.mark.anyio
async def test_update_fixture_score_rejects_missing_fixture() -> None:
    session = FakeSession([FakeResult(rowcount=0)])

    with pytest.raises(ValueError, match="Fixture not found"):
        await FixtureScoreBackfillRepository(session).update_fixture_score(
            fixture_id=999,
            status="FT",
            home_goals=2,
            away_goals=0,
            score_source="api_football_backfill",
        )
