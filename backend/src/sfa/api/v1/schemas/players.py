from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BreakdownEntrySchema(BaseModel):
    count: int
    pts: float
    pct: float | None = None


class PlayerDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    team: str
    position: str
    competition: str
    sfa_pts: float
    matches: int
    total_goals: int
    total_assists: int
    photo_url: str | None
    global_rank: int
    season: str
    breakdown: dict[str, BreakdownEntrySchema] | None
    competitions: list[str]
    available_seasons: list[str] = Field(default_factory=list)


class PlayerEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    competition: str
    stage: str
    fixture_id: int
    home_team: str
    away_team: str
    played_at: datetime
    minute: int
    event_type: str
    score_before: str | None
    score_diff: int | None
    m1: float
    m2: float
    m3: float
    m4: float
    mvisit: float
    pts: float


class PlayerFixtureSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fixture_id: int
    competition: str
    stage: str
    home_team: str
    away_team: str
    played_at: datetime
    sfa_pts: float
    events_count: int
    minutes: int = 0
    shots_on: int = 0
    dribbles_won: int = 0
    duels_won: int = 0
    tackles_won: int = 0
    interceptions: int = 0
    blocks: int = 0
    fouls_drawn: int = 0
    home_team_logo: str | None = None
    away_team_logo: str | None = None
    breakdown: dict[str, BreakdownEntrySchema] | None = None
    rating: float | None = None


class PlayerSeasonStatsSchema(BaseModel):
    player_id: int
    competition_id: int | None
    season: str
    matches: int
    minutes: int
    goals: int
    assists: int
    shots_total: int
    shots_on: int
    passes_total: int
    passes_accuracy_avg: float
    passes_key: int
    dribbles_won: int
    dribbles_attempts: int
    dribbles_past: int
    duels_won: int
    duels_total: int
    tackles_won: int
    interceptions: int
    blocks: int
    fouls_drawn: int
    fouls_committed: int
    cards_yellow: int
    cards_red: int
    penalty_won: int
    saves: int
    goals_conceded: int
    rating_avg: float | None
    dribble_success_rate: float | None
    duel_win_rate: float | None


class PlayerCompetitionAchievementSchema(BaseModel):
    achievement_id: int
    competition_id: int
    competition_name: str
    team_id: int
    team_name: str
    season: str
    phase: str
    title_count: int = Field(ge=0)
    bonus_pts: float = Field(ge=0)
