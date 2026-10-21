"""Read-only snapshot collector; also executable over SSH through stdin.

Only existing database rows and Redis values are read. No provider is constructed.
"""

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.redis_client import get_redis_client


async def collect(season: str) -> dict:
    redis = get_redis_client()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            players = (await session.execute(text(
                "SELECT id, external_id, name, position, position_source FROM players ORDER BY id"
            ))).mappings().all()
            fixtures = (await session.execute(text(
                "SELECT f.id, f.external_id, f.season, f.competition_id, f.played_at, f.status, "
                "h.external_id AS home_team_external_id, a.external_id AS away_team_external_id "
                "FROM fixtures f JOIN teams h ON h.id=f.home_team_id JOIN teams a ON a.id=f.away_team_id "
                "WHERE f.season=:season ORDER BY f.id"
            ), {"season": season})).mappings().all()
            versions = (await session.execute(text(
                "SELECT id, version, config_json FROM scoring_rules_versions WHERE is_active=true ORDER BY id"
            ))).mappings().all()
            caches = []
            seen_keys = set()
            async for key in redis.scan_iter(match="fixture:api:supplement:v2:*", count=200):
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                raw = await redis.get(key)
                if raw is not None:
                    caches.append({"key": key, "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                                   "payload": json.loads(raw)})
            await session.rollback()
        return {
            "schema": "sfa-position-audit-snapshot-v1", "season": season,
            "captured_at": datetime.now(timezone.utc).isoformat(), "read_only": True,
            "players": [dict(row) for row in players], "fixtures": [dict(row) for row in fixtures],
            "cache": sorted(caches, key=lambda item: item["key"]),
            "rules_fingerprint": hashlib.sha256(json.dumps(
                [dict(row) for row in versions], sort_keys=True, default=str
            ).encode()).hexdigest(),
            "starter_denominator_available": False,
        }
    finally:
        await redis.aclose()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(collect(sys.argv[1])), default=str, ensure_ascii=False))
