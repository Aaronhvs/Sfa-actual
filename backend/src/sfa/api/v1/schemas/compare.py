from pydantic import BaseModel

from sfa.api.v1.schemas.players import (
    PlayerDetailSchema,
    PlayerEventSchema,
    PlayerFixtureSchema,
    PlayerSeasonStatsSchema,
)


class ComparePlayerAnalyticsSchema(BaseModel):
    stats: PlayerSeasonStatsSchema | None
    events: list[PlayerEventSchema]
    fixtures: list[PlayerFixtureSchema]


class CompareResponseSchema(BaseModel):
    season: str
    scope: str | None = None
    player_a: PlayerDetailSchema
    player_b: PlayerDetailSchema
    player_a_analytics: ComparePlayerAnalyticsSchema
    player_b_analytics: ComparePlayerAnalyticsSchema
