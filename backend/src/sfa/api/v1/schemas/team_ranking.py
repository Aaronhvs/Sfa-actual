from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from sfa.api.v1.schemas.ranking import RankingPaginationSchema


class TeamRankingMatchSchema(BaseModel):
    fixture_external_id: int
    played_at: datetime
    opponent_name: str
    opponent_logo_url: str | None
    is_home: bool
    goals_for: int | None
    goals_against: int | None
    outcome: Literal["W", "D", "L"] | None
    status: str


class TeamRankingFeaturedPlayerSchema(BaseModel):
    id: int
    name: str
    photo_url: str | None
    individual_points: float
    appearances: int
    season: str


class RankedTeamSchema(BaseModel):
    rank: int
    id: int
    name: str
    team_logo_url: str | None
    competition_id: int
    competition: str
    score: float | None = Field(description="Experimental descriptive merit percentile, not predictive strength")
    elo_raw: float | None
    elo_score: float | None
    squad_score: float | None
    effective_elo_weight: float
    effective_squad_weight: float
    elo_season: str | None
    elo_source: str | None
    squad_season: str | None
    observed_players: int
    scored_players: int
    observed_appearances: int
    scored_appearances: int
    coverage: float | None = Field(description="Scored/observed appearances in squad_season; not roster completeness")
    squad_data_cutoff: datetime | None
    elo_data_cutoff: datetime | None = Field(description="Unknown: season summary has no reliable update timestamp")
    availability: None = Field(description="Unknown: no authoritative player availability data")
    recent_results: list[TeamRankingMatchSchema] = Field(default_factory=list)
    featured_player: TeamRankingFeaturedPlayerSchema | None = None


class TeamRankingModelSchema(BaseModel):
    version: str
    label: str
    descriptive_only: bool
    experimental: bool
    feeds_m1: bool
    elo_weight: float
    squad_weight: float
    recent_matches: int
    shrinkage_minutes: int
    rules_version_id: int | None
    population_teams: int
    participant_kind: str
    as_of: datetime = Field(description="Request timestamp, NOT the last ingestion/update timestamp")
    data_cutoff: datetime | None = Field(description="Latest scored fixture in the observed population")
    normalization: str
    sources: list[str]
    exclusions: list[str]
    attribution: str
    fallback: str
    caveats: list[str]


class TeamRankingResponseSchema(BaseModel):
    season: str
    scope: str | None
    total: int
    pagination: RankingPaginationSchema
    model: TeamRankingModelSchema
    ranking: list[RankedTeamSchema]
