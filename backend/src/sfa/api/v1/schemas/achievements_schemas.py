from pydantic import BaseModel, field_validator


class RegisterAchievementRequestSchema(BaseModel):
    competition_id: int
    team_id: int
    season: str
    phase: str
    rules_version_id: int
    competition_name: str = ""

    @field_validator("phase")
    @classmethod
    def phase_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("phase cannot be empty")
        return v


class RegisterAchievementResponseSchema(BaseModel):
    achievement_id: int
    status: str
    message: str


class CalculateAchievementBonusesRequestSchema(BaseModel):
    season: str
    competition_id: int
    rules_version_id: int


class CalculateAchievementBonusesResponseSchema(BaseModel):
    task_id: str
    status: str
    message: str


class CalculateTeamStrengthsRequestSchema(BaseModel):
    season: str
    competition_id: int
    matchday: int | None = None
    league_factor: float = 1.0


class CalculateTeamStrengthsResponseSchema(BaseModel):
    task_id: str
    status: str
    message: str


class TeamStrengthResponseSchema(BaseModel):
    team_id: int
    season: str
    competition_id: int
    strength: float
    source: str
