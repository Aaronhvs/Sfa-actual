from datetime import datetime, timezone

import pytest
from redis.exceptions import RedisError

from sfa.domain.matchday_mvp import MatchdayMvp, MvpFixture, MvpPlayer
from sfa.domain.ports import TournamentTeamDTO
from sfa.infrastructure.repositories.matchday_mvp_cache import MatchdayMvpCache


class FakeRedis:
    def __init__(self):
        self.data, self.ttls, self.fail = {}, {}, False

    async def get(self, key):
        if self.fail:
            raise RedisError("offline")
        return self.data.get(key)

    async def setex(self, key, ttl, value):
        if self.fail:
            raise RedisError("offline")
        self.data[key], self.ttls[key] = value, ttl


@pytest.mark.anyio
async def test_cache_roundtrip_empty_snapshot_version_keys_and_redis_failure():
    redis = FakeRedis()
    cache = MatchdayMvpCache(redis)
    team = TournamentTeamDTO(1, 529, "Barcelona")
    item = MatchdayMvp("matchday-1", "Jornada 1", 1, True, 0, MvpPlayer(34, "Lamine Yamal", team.name, "EXT", None),
                       3139.0, 1, 2, ("level",),
                       MvpFixture(1234, datetime(2026, 10, 26, tzinfo=timezone.utc), team, team, 1, 0, "home"))
    assert await cache.read("v1") is None
    await cache.write("v1", (item,))
    assert await cache.read("v1") == (item,)
    assert await cache.read("v2") is None
    await cache.write("empty", ())
    assert await cache.read("empty") == ()
    assert set(redis.ttls.values()) == {120}
    redis.data["matchday-mvps:corrupt"] = "{broken"
    assert await cache.read("corrupt") is None
    redis.fail = True
    assert await cache.read("v1") is None
    await cache.write("v1", (item,))
