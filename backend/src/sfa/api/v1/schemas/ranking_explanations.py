from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RankingPlayerExplanationSchema(BaseModel):
    id: int
    player_id: int
    player_name: str | None = None
    team_name: str | None = None
    team_logo_url: str | None = None
    season: str
    competition_id: int | None = None
    rules_version_id: int | None = None
    scope: str
    rank: int
    variant: str
    status: str
    short_text: str
    long_text: str
    bullets: list[str]
    evidence: dict[str, Any]
    model_name: str | None = None
    prompt_version: str
    generated_at: datetime


class RankingExplanationsResponseSchema(BaseModel):
    season: str
    scope: str
    explanations: list[RankingPlayerExplanationSchema]


class GenerateRankingExplanationsRequestSchema(BaseModel):
    season: str
    competition_id: int | None = None
    rules_version_id: int | None = None
    scope: str = "ranking"
    limit: int = Field(default=10, ge=1, le=10)
    force: bool = False
    use_total: bool = True


class GenerateRankingExplanationsQueuedSchema(BaseModel):
    task_id: str
    status: str = "queued"
