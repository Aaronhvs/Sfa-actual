import json
import logging
import secrets
from datetime import datetime, timezone

from redis.exceptions import RedisError

from sfa.domain.player_leads import (
    LeadGroup,
    LeadGroupKind,
    LeadMethod,
    LeadMetric,
    LeadThreshold,
    PlayerLead,
    PlayerLeadsCacheProtocol,
    PlayerLeadsSnapshot,
)

logger = logging.getLogger(__name__)

KEY_PREFIX = "player-leads"
LOCK_PREFIX = "player-leads-lock"
META_FIELD = "__meta__"
SNAPSHOT_TTL_SECONDS = 12 * 60 * 60
LOCK_TTL_SECONDS = 120
_CACHE_ERRORS = (RedisError, ConnectionError, OSError, TimeoutError)


def lead_to_dict(lead: PlayerLead) -> dict:
    return {
        "metric": lead.metric.value,
        "group": {
            "kind": lead.group.kind.value, "season": lead.group.season, "competition_id": lead.group.competition_id,
            "competition_name": lead.group.competition_name, "position": lead.group.position,
        },
        "rank": lead.rank,
        "tied": lead.tied,
        "qualified_count": lead.qualified_count,
        "value": lead.value,
        "ranking_value": lead.ranking_value,
        "method": lead.method.value,
        "numerator": lead.numerator,
        "denominator": lead.denominator,
        "threshold": {
            "min_minutes": lead.threshold.min_minutes, "min_attempts": lead.threshold.min_attempts,
            "attempts_kind": lead.threshold.attempts_kind, "min_events": lead.threshold.min_events,
        },
        "details": dict(lead.details),
    }


def lead_from_dict(data: dict) -> PlayerLead:
    group = data["group"]
    return PlayerLead(
        metric=LeadMetric(data["metric"]),
        group=LeadGroup(LeadGroupKind(group["kind"]), group["season"], group["competition_id"],
                        group["competition_name"], group["position"]),
        rank=data["rank"],
        tied=data["tied"],
        qualified_count=data["qualified_count"],
        value=data["value"],
        ranking_value=data["ranking_value"],
        method=LeadMethod(data["method"]),
        numerator=data["numerator"],
        denominator=data["denominator"],
        threshold=LeadThreshold(**data["threshold"]),
        details=data["details"],
    )


class PlayerLeadsCache(PlayerLeadsCacheProtocol):
    """One Redis hash per scope snapshot: a field per player plus a meta field marking it complete."""

    def __init__(self, redis) -> None:
        self._redis = redis

    async def read_player(self, key: str, player_id: int) -> tuple[PlayerLead, ...] | None:
        try:
            meta, raw = await self._redis.hmget(f"{KEY_PREFIX}:{key}", [META_FIELD, str(player_id)])
        except _CACHE_ERRORS as exc:
            logger.warning("[PlayerLeadsCache] Read failed for %s: %s", key, exc)
            return None
        if meta is None:
            return None
        return tuple(lead_from_dict(item) for item in json.loads(raw)) if raw else ()

    async def save_snapshot(self, key: str, snapshot: PlayerLeadsSnapshot) -> None:
        mapping = {str(player_id): json.dumps([lead_to_dict(lead) for lead in leads])
                   for player_id, leads in snapshot.leads_by_player.items()}
        mapping[META_FIELD] = json.dumps({
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "players_with_leads": len(snapshot.leads_by_player),
            "policy_version": snapshot.policy_version,
        })
        name = f"{KEY_PREFIX}:{key}"
        try:
            await self._redis.hset(name, mapping=mapping)
            await self._redis.expire(name, SNAPSHOT_TTL_SECONDS)
        except _CACHE_ERRORS as exc:
            logger.warning("[PlayerLeadsCache] Write failed for %s: %s", key, exc)

    async def acquire_lock(self, key: str) -> str | None:
        token = secrets.token_hex(8)
        try:
            acquired = await self._redis.set(f"{LOCK_PREFIX}:{key}", token, nx=True, ex=LOCK_TTL_SECONDS)
        except _CACHE_ERRORS as exc:
            logger.warning("[PlayerLeadsCache] Lock failed for %s: %s", key, exc)
            return None
        return token if acquired else None

    async def release_lock(self, key: str, token: str) -> None:
        name = f"{LOCK_PREFIX}:{key}"
        try:
            if await self._redis.get(name) == token:
                await self._redis.delete(name)
        except _CACHE_ERRORS as exc:
            logger.warning("[PlayerLeadsCache] Unlock failed for %s: %s", key, exc)
