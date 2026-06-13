import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

import redis.asyncio as aioredis

from sfa.api.v1.schemas.wc_schemas import (
    WcFixtureSchema,
    WcFixturesResponseSchema,
    WcLiveResponseSchema,
    WcTeamSchema,
)
from sfa.infrastructure.database import get_db
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.teams.models import Team
from sfa.infrastructure.redis_client import get_redis

router = APIRouter()

_CACHE_FIXTURES = "wc:fixtures:2026"
_CACHE_LIVE = "wc:live:2026"
_TTL_FIXTURES = 900   # 15 min — schedule rarely changes
_TTL_LIVE = 60        # 1 min — live status needs freshness
_LIVE_WINDOW_MINUTES = 130  # 90 + 40 buffer for extra time / delays
_WC_SEASON = "2026"


def _is_live(played_at: datetime) -> bool:
    now = datetime.now(timezone.utc)
    end = played_at + timedelta(minutes=_LIVE_WINDOW_MINUTES)
    return played_at <= now <= end


async def _fetch_wc_fixtures(db: AsyncSession) -> list[WcFixtureSchema]:
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

    stmt = (
        select(
            Fixture.id,
            Fixture.external_id,
            Fixture.stage,
            Fixture.matchday,
            Fixture.played_at,
            HomeTeam.id.label("home_id"),
            HomeTeam.name.label("home_name"),
            HomeTeam.external_id.label("home_ext_id"),
            AwayTeam.id.label("away_id"),
            AwayTeam.name.label("away_name"),
            AwayTeam.external_id.label("away_ext_id"),
        )
        .join(Competition, Competition.id == Fixture.competition_id)
        .join(HomeTeam, HomeTeam.id == Fixture.home_team_id)
        .join(AwayTeam, AwayTeam.id == Fixture.away_team_id)
        .where(
            Competition.participant_kind == "national_team",
            Fixture.season == _WC_SEASON,
        )
        .order_by(Fixture.played_at, Fixture.id)
    )

    rows = (await db.execute(stmt)).all()

    return [
        WcFixtureSchema(
            id=r.id,
            external_id=r.external_id,
            stage=r.stage,
            matchday=r.matchday,
            played_at=r.played_at,
            is_live=_is_live(r.played_at),
            home_team=WcTeamSchema(id=r.home_id, name=r.home_name, external_id=r.home_ext_id),
            away_team=WcTeamSchema(id=r.away_id, name=r.away_name, external_id=r.away_ext_id),
        )
        for r in rows
    ]


@router.get("/wc/fixtures", response_model=WcFixturesResponseSchema, tags=["mundial"])
async def get_wc_fixtures(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> WcFixturesResponseSchema:
    cached = await redis.get(_CACHE_FIXTURES)
    if cached:
        data = json.loads(cached)
        return WcFixturesResponseSchema(**data)

    fixtures = await _fetch_wc_fixtures(db)
    response = WcFixturesResponseSchema(fixtures=fixtures, season=_WC_SEASON)
    await redis.setex(_CACHE_FIXTURES, _TTL_FIXTURES, response.model_dump_json())
    return response


@router.get("/wc/live", response_model=WcLiveResponseSchema, tags=["mundial"])
async def get_wc_live(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> WcLiveResponseSchema:
    cached = await redis.get(_CACHE_LIVE)
    if cached:
        data = json.loads(cached)
        return WcLiveResponseSchema(**data)

    fixtures = await _fetch_wc_fixtures(db)
    live = [f for f in fixtures if f.is_live]
    response = WcLiveResponseSchema(live=live, has_live=len(live) > 0)
    await redis.setex(_CACHE_LIVE, _TTL_LIVE, response.model_dump_json())
    return response
