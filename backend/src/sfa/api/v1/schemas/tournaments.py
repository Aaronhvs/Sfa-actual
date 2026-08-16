from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from sfa.api.v1.schemas.wc_schemas import (
    WcFixtureDetailResponseSchema,
    WcFixtureEventSchema,
    WcFixtureSchema,
    WcLineupPlayerSchema,
    WcStatisticSchema,
    WcTeamLineupSchema,
    WcTeamSchema,
    WcVenueSchema,
)

TournamentMatchTeamSchema = WcTeamSchema
TournamentMatchFixtureSchema = WcFixtureSchema
TournamentMatchVenueSchema = WcVenueSchema
TournamentMatchLineupPlayerSchema = WcLineupPlayerSchema
TournamentMatchTeamLineupSchema = WcTeamLineupSchema
TournamentMatchStatisticSchema = WcStatisticSchema
TournamentMatchEventSchema = WcFixtureEventSchema
TournamentMatchDetailResponseSchema = WcFixtureDetailResponseSchema


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
