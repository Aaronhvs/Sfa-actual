from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from sfa.api.v1.schemas.tournaments import TournamentCompetitionSchema


class MvpPlayerSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    team: str
    position: str
    photo_url: str | None


class MvpTeamSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_id: int | None
    name: str


class MvpFixtureSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    external_id: int
    played_at: datetime
    home_team: MvpTeamSchema
    away_team: MvpTeamSchema
    home_goals: int | None
    away_goals: int | None
    player_side: Literal["home", "away"]


class MatchdayMvpSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    round_key: str
    round_label: str
    matchday: int | None
    complete: bool
    pending_fixtures: int
    player: MvpPlayerSchema
    sfa_pts: float
    goals: int
    assists: int
    reasons: list[Literal["behind", "level", "big_rival", "away", "knockout"]]
    fixture: MvpFixtureSchema


class TournamentMvpsResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    competition_id: int
    season: str
    items: list[MatchdayMvpSchema]


class LatestTournamentMvpSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    competition: TournamentCompetitionSchema
    mvp: MatchdayMvpSchema


class LatestTournamentMvpsResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    season: str
    items: list[LatestTournamentMvpSchema]
