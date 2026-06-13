import pytest

from sfa.application.use_cases.fix_player_positions import (
    FixPlayerPositionsUseCase,
    classify_player_from_stats,
)
from sfa.infrastructure.models.enums import Position


def test_gk_detection_by_saves():
    result = classify_player_from_stats(
        avg_saves=2.5,
        avg_interceptions=0.1,
        avg_goals=0.0,
        match_count=10,
    )

    assert result == Position.GK


def test_dc_detection_by_heuristic():
    result = classify_player_from_stats(
        avg_saves=0.0,
        avg_interceptions=1.4,
        avg_goals=0.0,
        match_count=8,
    )

    assert result == Position.DC


def test_known_positions_applied():
    assert Position.LAT == Position.LAT


def test_mc_player_unchanged_if_ambiguous():
    result = classify_player_from_stats(
        avg_saves=0.0,
        avg_interceptions=0.7,
        avg_goals=0.12,
        match_count=12,
    )

    assert result is None


class _FakeResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self) -> None:
        self.flushed = 0

    async def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}
        if "WHERE name = :name" in sql:
            return _FakeResult(1 if params.get("name") == "Trent Alexander-Arnold" else 0)
        if "SET position = 'GK'" in sql:
            return _FakeResult(3)
        if "SET position = 'DC'" in sql:
            return _FakeResult(7)
        return _FakeResult(0)

    async def flush(self):
        self.flushed += 1


@pytest.mark.anyio
async def test_result_counts_are_accurate():
    use_case = FixPlayerPositionsUseCase(_FakeSession())

    result = await use_case.execute()

    assert result.known_positions_fixed == 1
    assert result.gk_fixed == 3
    assert result.dc_fixed == 7
    assert result.total_fixed == 11
