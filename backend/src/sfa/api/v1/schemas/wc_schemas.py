from datetime import datetime

from pydantic import BaseModel


class WcTeamSchema(BaseModel):
    id: int
    name: str
    external_id: int | None = None


class WcFixtureSchema(BaseModel):
    id: int
    external_id: int
    stage: str
    matchday: int | None
    played_at: datetime
    is_live: bool
    status: str
    status_label: str
    elapsed: int | None
    home_goals: int | None
    away_goals: int | None
    home_team: WcTeamSchema
    away_team: WcTeamSchema


class WcFixturesResponseSchema(BaseModel):
    fixtures: list[WcFixtureSchema]
    season: str


class WcLiveResponseSchema(BaseModel):
    live: list[WcFixtureSchema]
    has_live: bool


class WcStandingSchema(BaseModel):
    group: str
    position: int
    team: WcTeamSchema
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    form: str | None


class WcStandingsResponseSchema(BaseModel):
    standings: list[WcStandingSchema]
    season: str


class WcVenueSchema(BaseModel):
    name: str | None
    city: str | None


class WcLineupPlayerSchema(BaseModel):
    external_id: int | None
    name: str
    number: int | None
    position: str | None
    grid: str | None
    player_id: int | None
    sfa_points: float | None


class WcTeamLineupSchema(BaseModel):
    team: WcTeamSchema
    formation: str | None
    coach_name: str | None
    coach_photo: str | None
    start_xi: list[WcLineupPlayerSchema]
    substitutes: list[WcLineupPlayerSchema]


class WcStatisticSchema(BaseModel):
    label: str
    home_value: str | None
    away_value: str | None
    home_numeric: float | None
    away_numeric: float | None


class WcFixtureEventSchema(BaseModel):
    minute: int
    extra_minute: int
    team_external_id: int
    event_type: str
    player_name: str
    assist_name: str | None


class WcFixtureDetailResponseSchema(BaseModel):
    fixture: WcFixtureSchema
    venue: WcVenueSchema
    referee: str | None
    lineups: list[WcTeamLineupSchema]
    statistics: list[WcStatisticSchema]
    events: list[WcFixtureEventSchema] = []
