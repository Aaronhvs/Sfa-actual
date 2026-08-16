from datetime import datetime, timezone

import pytest

from sfa.domain.fixture_detail_ports import (
    FixtureDetailDTO,
    FixtureSummaryDTO,
    FixtureTeamDTO,
    FixtureVenueDTO,
)
from sfa.infrastructure.repositories.fixture_detail_repository import (
    FixtureDetailRepository,
)


def _detail() -> FixtureDetailDTO:
    return FixtureDetailDTO(
        fixture=FixtureSummaryDTO(
            external_id=1570338,
            stage="Regular Season - 1",
            matchday=1,
            played_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
            status="FT",
            status_label="Match Finished",
            elapsed=90,
            home_team=FixtureTeamDTO(540, "Espanyol"),
            away_team=FixtureTeamDTO(539, "Levante"),
            home_goals=3,
            away_goals=0,
        ),
        venue=FixtureVenueDTO("RCDE Stadium", "Cornella"),
        referee=None,
        lineups=[],
        statistics=[],
    )


class FakeRedis:
    def __init__(self) -> None:
        self.read_keys = []
        self.writes = []

    async def get(self, key):
        self.read_keys.append(key)
        return None

    async def setex(self, key, ttl, value):
        self.writes.append((key, ttl, value))


class FakeProvider:
    def __init__(self, detail=None, error=None) -> None:
        self.detail = detail
        self.error = error

    async def fetch_fixture_detail(self, fixture_external_id):
        if self.error:
            raise self.error
        return self.detail


class FakeMappings:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeResult:
    def __init__(self, rows) -> None:
        self.rows = rows

    def mappings(self):
        return FakeMappings(self.rows)


class FakeSession:
    def __init__(self, rows=None) -> None:
        self.rows = rows or []
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeResult(self.rows)


@pytest.mark.anyio
async def test_uses_versioned_supplement_cache_key():
    redis = FakeRedis()
    repository = FixtureDetailRepository(
        FakeProvider(_detail()),
        redis,
        FakeSession(),
    )

    result = await repository.get_fixture_detail(1570338)

    assert result is not None
    assert redis.read_keys == ["fixture:api:supplement:v2:1570338"]
    assert redis.writes[0][0] == "fixture:api:supplement:v2:1570338"


@pytest.mark.anyio
async def test_returns_none_when_supplement_provider_fails():
    repository = FixtureDetailRepository(
        FakeProvider(error=RuntimeError("upstream unavailable")),
        FakeRedis(),
        FakeSession(),
    )

    assert await repository.get_fixture_detail(1570338) is None


@pytest.mark.anyio
async def test_maps_sfa_momentum_buckets_for_both_teams():
    session = FakeSession([
        {"minute_start": 0, "home_points": 120.25, "away_points": 0},
        {"minute_start": 5, "home_points": 0, "away_points": 80.5},
    ])
    repository = FixtureDetailRepository(
        FakeProvider(),
        FakeRedis(),
        session,
    )

    result = await repository.get_fixture_sfa_momentum(10, 1, 2)

    assert [(item.minute_start, item.minute_end) for item in result] == [
        (0, 5),
        (5, 10),
    ]
    assert result[0].home_points == 120.25
    assert result[1].away_points == 80.5
    assert len(session.statements) == 1
