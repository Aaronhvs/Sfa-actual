from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TournamentMatchTeamSchema(BaseModel):
    id: int
    name: str
    external_id: int | None = None


class TournamentMatchFixtureSchema(BaseModel):
    id: int
    external_id: int
    competition_id: int | None = None
    competition_name: str | None = None
    stage: str
    matchday: int | None
    played_at: datetime
    is_live: bool
    status: str
    status_label: str
    elapsed: int | None
    home_goals: int | None
    away_goals: int | None
    home_winner: bool | None = None
    away_winner: bool | None = None
    home_team: TournamentMatchTeamSchema
    away_team: TournamentMatchTeamSchema


class TournamentMatchVenueSchema(BaseModel):
    name: str | None
    city: str | None


class TournamentMatchLineupPlayerSchema(BaseModel):
    external_id: int | None
    name: str
    number: int | None
    position: str | None
    grid: str | None
    player_id: int | None
    sfa_points: float | None


class TournamentMatchTeamLineupSchema(BaseModel):
    team: TournamentMatchTeamSchema
    formation: str | None
    coach_name: str | None
    coach_photo: str | None
    start_xi: list[TournamentMatchLineupPlayerSchema]
    substitutes: list[TournamentMatchLineupPlayerSchema]


class TournamentMatchStatisticSchema(BaseModel):
    label: str
    home_value: str | None
    away_value: str | None
    home_numeric: float | None
    away_numeric: float | None


class TournamentMatchEventSchema(BaseModel):
    minute: int
    extra_minute: int
    team_external_id: int
    event_type: str
    player_name: str
    assist_name: str | None


class TournamentMatchMomentumBucketSchema(BaseModel):
    minute_start: int
    minute_end: int
    home_points: float
    away_points: float


class TournamentMatchDetailResponseSchema(BaseModel):
    fixture: TournamentMatchFixtureSchema
    venue: TournamentMatchVenueSchema
    referee: str | None
    lineups: list[TournamentMatchTeamLineupSchema]
    statistics: list[TournamentMatchStatisticSchema]
    events: list[TournamentMatchEventSchema] = Field(default_factory=list)
    sfa_momentum: list[TournamentMatchMomentumBucketSchema] = Field(
        default_factory=list,
    )


class TournamentCompetitionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    season: str
    participant_kind: str
    total_fixtures: int
    completed_fixtures: int
    upcoming_fixtures: int


class TournamentTeamSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: int | None
    name: str


class TournamentFixtureSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: int
    competition_id: int
    stage: str
    matchday: int | None
    played_at: datetime
    status: str
    home_goals: int | None
    away_goals: int | None
    home_team: TournamentTeamSchema
    away_team: TournamentTeamSchema


class TournamentStandingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    team: TournamentTeamSchema
    points: int


class TournamentCatalogResponseSchema(BaseModel):
    season: str
    competitions: list[TournamentCompetitionSchema]


class TournamentDetailResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    competition: TournamentCompetitionSchema
    standings_matchday: int | None
    fixtures: list[TournamentFixtureSchema]
    standings: list[TournamentStandingSchema]
    champion: TournamentTeamSchema | None = None


class TournamentFixtureGroupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    competition: TournamentCompetitionSchema
    fixtures: list[TournamentFixtureSchema]


class TournamentDashboardResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: str
    selected_date: date | None
    previous_date: date | None
    next_date: date | None
    groups: list[TournamentFixtureGroupSchema]
