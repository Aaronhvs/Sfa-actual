from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class TeamRankingInputDTO:
    id: int
    name: str
    external_id: int | None
    competition_id: int
    competition: str
    competition_ids: tuple[int, ...]


@dataclass(frozen=True)
class TeamRankingEloDTO:
    team_id: int
    season: str
    elo_raw: float
    source: str


@dataclass(frozen=True)
class TeamRankingPlayerDTO:
    team_id: int
    player_id: int
    season: str
    position: str
    observed_appearances: int
    scored_appearances: int
    scored_minutes: int
    individual_points: float | None
    data_cutoff: datetime | None = None


@dataclass(frozen=True)
class TeamRankingDataDTO:
    teams: tuple[TeamRankingInputDTO, ...] = ()
    elos: tuple[TeamRankingEloDTO, ...] = ()
    players: tuple[TeamRankingPlayerDTO, ...] = ()
    rules_version_id: int | None = None


@dataclass(frozen=True)
class RankedTeamDTO:
    rank: int
    id: int
    name: str
    team_logo_url: str | None
    competition_id: int
    competition: str
    score: float | None
    elo_raw: float | None
    elo_score: float | None
    squad_score: float | None
    effective_elo_weight: float
    effective_squad_weight: float
    elo_season: str | None
    elo_source: str | None
    squad_season: str | None
    observed_players: int
    scored_players: int
    observed_appearances: int
    scored_appearances: int
    coverage: float | None
    squad_data_cutoff: datetime | None = None
    elo_data_cutoff: datetime | None = None
    availability: None = None


@runtime_checkable
class TeamRankingRepositoryProtocol(Protocol):
    async def latest_season(self, participant_kind: str) -> str | None: ...

    async def get_ranking_data(
        self, season: str, prior_season: str, participant_kind: str,
        as_of: datetime, recent_matches: int,
    ) -> TeamRankingDataDTO: ...
