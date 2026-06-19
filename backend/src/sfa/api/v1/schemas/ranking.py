from pydantic import BaseModel, ConfigDict


class RankedPlayerSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    id: int
    name: str
    team: str
    team_logo_url: str | None = None
    position: str
    competition: str
    sfa_pts: float
    matches: int
    photo_url: str | None
    goals: int = 0
    assists: int = 0
    dribbles_won: int = 0
    duels_won: int = 0
    b1_bonus_pts: float = 0.0
    b1_bonus_label: str | None = None


class RankingResponseSchema(BaseModel):
    season: str
    total: int
    ranking: list[RankedPlayerSchema]
