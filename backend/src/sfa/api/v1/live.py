from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from sfa.core.dependencies import get_redis
from sfa.infrastructure.live_teams import read_live_teams

router = APIRouter()


class LiveTeamsSchema(BaseModel):
    team_ids: list[int]
    updated_at: int | None = None


@router.get("/live/teams", response_model=LiveTeamsSchema)
async def get_live_teams(
    response: Response,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> LiveTeamsSchema:
    """External ids of teams with a match in progress (snapshot from the live cycle)."""
    response.headers["Cache-Control"] = "public, max-age=60"
    try:
        team_ids, updated_at = await read_live_teams(redis)
    except Exception:
        team_ids, updated_at = [], None
    return LiveTeamsSchema(team_ids=team_ids, updated_at=updated_at)
