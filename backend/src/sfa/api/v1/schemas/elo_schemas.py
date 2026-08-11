from typing import Literal

from pydantic import BaseModel, Field


class ManualClubEloSchema(BaseModel):
    team_name: str
    elo_raw: float = Field(gt=0)
    reason: str = Field(min_length=3, max_length=255)


class SeedClubEloRequest(BaseModel):
    date_str: str
    season: str
    manual_entries: list[ManualClubEloSchema] | None = None


class SeedClubEloResponse(BaseModel):
    date_str: str
    season: str
    matched: int
    unmatched: list[str]
    status: str
    error: str | None


class ManualNationalTeamEloSchema(BaseModel):
    country_name: str
    elo_raw: float
    rank: int | None = None
    source_date: str | None = None


class SeedNationalTeamEloRequest(BaseModel):
    season: str
    competition_id: int | None = None
    source_url: str | None = None
    dry_run: bool = True
    min_coverage: float = 100.0
    manual_entries: list[ManualNationalTeamEloSchema] | None = None


class SeedNationalTeamEloResponse(BaseModel):
    season: str
    competition_id: int | None
    matched: int
    total_teams: int
    coverage_pct: float
    unmatched: list[str]
    source_date: str | None
    dry_run: bool
    status: str
    error: str | None


class NationalTeamEloCoverageRowSchema(BaseModel):
    team_id: int
    team_name: str
    competition_id: int
    strength: float | None
    elo_raw: float | None
    source: str | None


class NationalTeamEloCoverageResponse(BaseModel):
    season: str
    competition_id: int | None
    total_teams: int
    teams_with_strength: int
    missing: list[str]
    coverage_pct: float
    rows: list[NationalTeamEloCoverageRowSchema]
    status: str
    error: str | None


class RecalculateEloRequest(BaseModel):
    season: str
    competition_ids: list[int]
    k_factors: dict[int, float] = Field(default_factory=dict)
    default_k: float = 30.0
    participant_kind: Literal["club", "national_team"] = "club"


class RecalculateEloResponse(BaseModel):
    season: str
    fixtures_processed: int
    teams_updated: int
    status: str
    error: str | None
