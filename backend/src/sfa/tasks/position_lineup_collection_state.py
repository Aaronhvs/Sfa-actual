from __future__ import annotations

import uuid
from collections.abc import Callable

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class PositionLineupCollectionStateAdapter:
    """Input-side checkpoints commit before each external request.

    A shared lease covers every competition/season in the collector. Atomic
    owner comparison prevents an expired worker from releasing another's lease.
    Other ingestion workers still consume the same upstream account, so headers
    are checked before every call; unknown quota stops acquisition.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession], repository_factory: Callable,
                 redis: Redis, lease_key: str = "position-lineups:acquisition:lease") -> None:
        self._sessions = sessions
        self._factory = repository_factory
        self._redis = redis
        self._key = lease_key
        self._token = uuid.uuid4().hex

    async def acquire(self) -> bool:
        return bool(await self._redis.set(self._key, self._token, nx=True, ex=900))

    async def owns_lease(self) -> bool:
        token = await self._redis.get(self._key)
        return token == self._token or token == self._token.encode()

    async def release(self) -> None:
        await self._redis.eval(
            "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
            1, self._key, self._token,
        )

    async def pending(self, season: str, limit: int) -> tuple[int, ...]:
        async with self._sessions() as session:
            return await self._factory(session).pending_lineups(season, limit)

    async def checkpoint(self, fixture_id: int | None, state: str, details_json: str) -> None:
        async with self._sessions() as session, session.begin():
            await self._factory(session).checkpoint_collection(fixture_id, state, details_json)

    async def inventory(self, competition_id: int, season: str) -> str:
        async with self._sessions() as session:
            return await self._factory(session).coverage_inventory(competition_id, season)

    async def record_calendar(self, scope_key: str, proof_json: str, status: str) -> None:
        async with self._sessions() as session, session.begin():
            await self._factory(session).record_calendar(scope_key, proof_json, status)
