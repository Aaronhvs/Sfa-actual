from pydantic import BaseModel, Field


class SeedClubEloRequest(BaseModel):
    date_str: str
    season: str


class SeedClubEloResponse(BaseModel):
    date_str: str
    season: str
    matched: int
    unmatched: list[str]
    status: str
    error: str | None


class RecalculateEloRequest(BaseModel):
    season: str
    competition_ids: list[int]
    k_factors: dict[int, float] = Field(default_factory=dict)
    default_k: float = 30.0


class RecalculateEloResponse(BaseModel):
    season: str
    fixtures_processed: int
    teams_updated: int
    status: str
    error: str | None
