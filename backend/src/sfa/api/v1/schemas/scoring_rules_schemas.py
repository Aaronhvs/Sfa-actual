from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class ScoringRulesVersionResponseSchema(BaseModel):
    id: int
    name: str
    version: str
    description: str | None
    is_active: bool
    config_json: dict
    created_at: datetime


class CreateScoringRulesVersionRequestSchema(BaseModel):
    name: str
    version: str
    description: str = ""
    config_json: dict

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v

    @field_validator("version")
    @classmethod
    def version_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("version cannot be empty")
        return v


class RecalculateRequestSchema(BaseModel):
    rules_version_id: int
    season: str
    competition_id: int | None = None
    match_id: int | None = None
    player_id: int | None = None
    force_recalculate: bool = False


class RecalculateResponseSchema(BaseModel):
    task_id: str
    status: str
    message: str


class InferAchievementsRequestSchema(BaseModel):
    competition_id: int
    season: str
    rules_version_id: int


class InferAchievementsAllRequestSchema(BaseModel):
    season: str
    rules_version_id: int


class InferAchievementsResponseSchema(BaseModel):
    task_id: str
    status: str
    message: str
