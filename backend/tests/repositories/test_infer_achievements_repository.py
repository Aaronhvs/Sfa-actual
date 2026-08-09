from __future__ import annotations

import pytest

from sfa.infrastructure.repositories.infer_achievements_repository import (
    InferAchievementsRepository,
)


class FakeResult:
    def __init__(
        self,
        *,
        rows: list[object] | None = None,
        mapping: dict[str, object] | None = None,
    ) -> None:
        self._rows = rows or []
        self._mapping = mapping

    def all(self) -> list[object]:
        return self._rows

    def mappings(self) -> FakeResult:
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self._mapping


class FakeSession:
    def __init__(self, results: list[FakeResult]) -> None:
        self._results = results
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return self._results.pop(0)


@pytest.mark.anyio
async def test_shootout_goals_fall_back_to_raw_fixture_events_for_penalty_result() -> None:
    session = FakeSession([
        FakeResult(rows=[]),
        FakeResult(mapping={
            "fixture_external_id": 9001,
            "status": "PEN",
            "home_team_id": 10,
            "away_team_id": 20,
            "home_team_external_id": 100,
            "away_team_external_id": 200,
        }),
        FakeResult(rows=[(100,), (200,), (100,), (200,), (100,), (200,), (100,)]),
    ])

    result = await InferAchievementsRepository(session).get_shootout_goals_for_fixture(55)

    assert result == {10: 4, 20: 3}
    assert len(session.statements) == 3
    assert "fixture_events" in str(session.statements[2])


@pytest.mark.anyio
async def test_shootout_goals_keep_scored_events_for_non_penalty_fixture() -> None:
    session = FakeSession([
        FakeResult(rows=[(10,), (20,), (10,)]),
        FakeResult(mapping={
            "fixture_external_id": 9002,
            "status": "AET",
            "home_team_id": 10,
            "away_team_id": 20,
            "home_team_external_id": 100,
            "away_team_external_id": 200,
        }),
    ])

    result = await InferAchievementsRepository(session).get_shootout_goals_for_fixture(56)

    assert result == {10: 2, 20: 1}
    assert len(session.statements) == 2
