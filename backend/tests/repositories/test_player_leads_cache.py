import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from sfa.domain.player_leads import (
    LeadGroup,
    LeadGroupKind,
    LeadMethod,
    LeadMetric,
    LeadThreshold,
    PlayerLead,
    PlayerLeadsSnapshot,
)
from sfa.infrastructure.repositories.player_leads_cache import (
    LOCK_PREFIX,
    SNAPSHOT_TTL_SECONDS,
    PlayerLeadsCache,
    lead_from_dict,
    lead_to_dict,
)


class FakeRedis:
    """In-memory subset of redis.asyncio used by the adapter."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def hmget(self, name, fields):
        stored = self.hashes.get(name, {})
        return [stored.get(field) for field in fields]

    async def hset(self, name, mapping):
        self.hashes.setdefault(name, {}).update(mapping)

    async def expire(self, name, seconds):
        self.ttls[name] = seconds

    async def set(self, name, value, nx=False, ex=None):
        if nx and name in self.values:
            return None
        self.values[name] = value
        return True

    async def get(self, name):
        return self.values.get(name)

    async def delete(self, name):
        self.values.pop(name, None)


class BrokenRedis:
    async def _fail(self, *args, **kwargs):
        raise RedisConnectionError("down")

    hmget = hset = expire = set = get = delete = _fail


LEAD = PlayerLead(
    LeadMetric.SHOT_CONVERSION, LeadGroup(LeadGroupKind.COMPETITION, "2025", 140, "La Liga"), 1, False, 38,
    0.737, 0.512, LeadMethod.WILSON_LOWER_BOUND, 14, 19, LeadThreshold(1026, 8, "shots_on_target", 3),
    {"penalty_goals_excluded": 0},
)
SNAPSHOT = PlayerLeadsSnapshot("leads-v2", "season-2025", 7, {35: (LEAD,)})


def test_serialization_round_trip():
    assert lead_from_dict(lead_to_dict(LEAD)) == LEAD


@pytest.mark.anyio
async def test_save_and_read_player():
    redis = FakeRedis()
    cache = PlayerLeadsCache(redis)
    assert await cache.read_player("k", 35) is None
    await cache.save_snapshot("k", SNAPSHOT)
    assert await cache.read_player("k", 35) == (LEAD,)
    assert await cache.read_player("k", 99) == ()  # snapshot exists, player leads nothing
    assert SNAPSHOT_TTL_SECONDS in redis.ttls.values()


@pytest.mark.anyio
async def test_lock_is_exclusive_and_only_released_by_owner():
    redis = FakeRedis()
    cache = PlayerLeadsCache(redis)
    token = await cache.acquire_lock("k")
    assert token is not None
    assert await cache.acquire_lock("k") is None
    await cache.release_lock("k", "someone-else")
    assert redis.values[f"{LOCK_PREFIX}:k"] == token
    await cache.release_lock("k", token)
    assert f"{LOCK_PREFIX}:k" not in redis.values


@pytest.mark.anyio
async def test_redis_errors_degrade_to_cache_miss():
    cache = PlayerLeadsCache(BrokenRedis())
    assert await cache.read_player("k", 35) is None
    assert await cache.acquire_lock("k") is None
    await cache.save_snapshot("k", SNAPSHOT)
    await cache.release_lock("k", "token")
