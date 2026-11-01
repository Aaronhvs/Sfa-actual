import json
import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from sfa.api.v1.live import router
from sfa.core.dependencies import get_redis
from sfa.infrastructure.live_teams import LIVE_TEAMS_KEY, live_team_ids, read_live_teams


def _fixture(status: str, league_id: int = 140, home: int = 529, away: int = 541, ts: int = 1_000) -> dict:
    return {
        "fixture": {"status": {"short": status}, "timestamp": ts},
        "league": {"id": league_id},
        "teams": {"home": {"id": home}, "away": {"id": away}},
    }


def test_only_in_play_fixtures_of_known_leagues_count():
    fixtures = [
        _fixture("2H"),
        _fixture("HT", home=33, away=40, ts=2_000),
        _fixture("FT", home=50, away=42),
        _fixture("NS", home=157, away=165),
        _fixture("1H", league_id=999, home=1, away=2),
    ]

    assert live_team_ids(fixtures, {140}) == {529: 1_000, 541: 1_000, 33: 2_000, 40: 2_000}


def test_malformed_fixtures_are_ignored():
    fixtures = [
        {"fixture": {"status": {"short": "1H"}}, "league": {"id": 140}, "teams": {}},
        {},
    ]

    assert live_team_ids(fixtures, {140}) == {}


class FakeRedis:
    def __init__(self, value=None, *, unavailable=False):
        self.value = value
        self.unavailable = unavailable

    async def get(self, key):
        assert key == LIVE_TEAMS_KEY
        if self.unavailable:
            raise ConnectionError('Redis unavailable')
        return self.value


@pytest.mark.anyio
async def test_read_discards_stale_matches_and_sorts_external_ids():
    now = int(time.time())
    cache = FakeRedis(json.dumps({'updated_at': now, 'teams': {
        '541': now - 3600, '529': now - 3600, '33': now - 5 * 3600,
    }}))
    assert await read_live_teams(cache) == ([529, 541], now)


@pytest.mark.anyio
async def test_missing_snapshot_returns_no_teams():
    assert await read_live_teams(FakeRedis()) == ([], None)


@pytest.mark.anyio
@pytest.mark.parametrize('unavailable', [False, True])
async def test_endpoint_returns_snapshot_and_degrades_when_redis_is_unavailable(unavailable):
    now = int(time.time())
    cache = FakeRedis(json.dumps({'updated_at': now, 'teams': {'529': now - 60}}),
                      unavailable=unavailable)
    app = FastAPI()
    app.include_router(router, prefix='/api/v1')

    async def redis_dependency():
        return cache

    app.dependency_overrides[get_redis] = redis_dependency
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/api/v1/live/teams')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'public, max-age=60'
    assert response.json() == ({'team_ids': [], 'updated_at': None} if unavailable
                               else {'team_ids': [529], 'updated_at': now})
