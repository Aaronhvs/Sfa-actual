from datetime import datetime

from pydantic import BaseModel


class WcTeamSchema(BaseModel):
    id: int
    name: str
    external_id: int | None = None


class WcFixtureSchema(BaseModel):
    id: int
    external_id: int
    stage: str
    matchday: int | None
    played_at: datetime
    is_live: bool
    home_team: WcTeamSchema
    away_team: WcTeamSchema


class WcFixturesResponseSchema(BaseModel):
    fixtures: list[WcFixtureSchema]
    season: str


class WcLiveResponseSchema(BaseModel):
    live: list[WcFixtureSchema]
    has_live: bool
