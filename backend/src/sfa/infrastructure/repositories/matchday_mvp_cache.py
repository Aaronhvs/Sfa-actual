import json
import logging
from dataclasses import asdict
from datetime import datetime

from redis.exceptions import RedisError

from sfa.domain.matchday_mvp import MatchdayMvp, MatchdayMvpCacheProtocol, MvpFixture, MvpPlayer
from sfa.domain.ports import TournamentTeamDTO

logger = logging.getLogger(__name__)
CACHE_TTL = 120
CACHE_PREFIX = "matchday-mvps"
CACHE_ERRORS = (RedisError, ConnectionError, OSError, TimeoutError)


class MatchdayMvpCache(MatchdayMvpCacheProtocol):
    def __init__(self, redis) -> None:
        self._redis = redis

    async def read(self, key: str) -> tuple[MatchdayMvp, ...] | None:
        try:
            raw = await self._redis.get(f"{CACHE_PREFIX}:{key}")
            if raw is None:
                return None
            items = []
            decoded = json.loads(raw)
            if not isinstance(decoded, list) or any(not isinstance(item, dict) for item in decoded):
                raise ValueError("Invalid MVP cache payload")
            for item in decoded:
                fixture = item.pop("fixture")
                fixture["played_at"] = datetime.fromisoformat(fixture["played_at"])
                fixture["home_team"] = TournamentTeamDTO(**fixture["home_team"])
                fixture["away_team"] = TournamentTeamDTO(**fixture["away_team"])
                item["player"] = MvpPlayer(**item["player"])
                item["reasons"] = tuple(item["reasons"])
                items.append(MatchdayMvp(**item, fixture=MvpFixture(**fixture)))
            return tuple(items)
        except (*CACHE_ERRORS, ValueError, TypeError, KeyError) as exc:
            logger.warning("[MatchdayMvpCache] Read failed: %s", exc)
            return None

    async def write(self, key: str, items: tuple[MatchdayMvp, ...]) -> None:
        try:
            payload = json.dumps([asdict(item) for item in items], default=lambda value: value.isoformat())
            await self._redis.setex(f"{CACHE_PREFIX}:{key}", CACHE_TTL, payload)
        except CACHE_ERRORS as exc:
            logger.warning("[MatchdayMvpCache] Write failed: %s", exc)
