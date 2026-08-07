from pydantic import BaseModel


class FullRecalculateRequestSchema(BaseModel):
    rules_version_id: int
    season: str
    force_recalculate: bool = True
    infer_achievements: bool = True


class FullRecalculateResponseSchema(BaseModel):
    task_id: str
    status: str
    message: str


class AwardPeriodRecalculateRequestSchema(BaseModel):
    scope_key: str = "season-2025"
    rules_version_id: int
    force_recalculate: bool = True
    infer_achievements: bool = True


class AwardPeriodRecalculateResponseSchema(BaseModel):
    task_id: str
    status: str
    scope_key: str
    rules_version_id: int
