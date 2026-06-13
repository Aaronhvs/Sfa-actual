from pydantic import BaseModel


class FullRecalculateRequestSchema(BaseModel):
    rules_version_id: int
    season: str
    force_recalculate: bool = True


class FullRecalculateResponseSchema(BaseModel):
    task_id: str
    status: str
    message: str
