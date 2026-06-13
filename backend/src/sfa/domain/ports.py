from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

# ─── DTOs de dominio ─────────────────────────────────────────────────


@dataclass(frozen=True)
class PlayerDTO:
    id: int
    name: str
    position: str
    photo_url: str | None
    team_name: str


@dataclass(frozen=True)
class PlayerScoreDTO:
    """Fila principal de score de un jugador en una season/competition."""
    player_id: int
    player_name: str
    team_name: str
    position: str
    competition_name: str
    competition_id: int
    total_pts: float
    matches_played: int
    photo_url: str | None
    breakdown: dict | None


@dataclass(frozen=True)
class RankedPlayerDTO:
    rank: int
    player_id: int
    player_name: str
    team_name: str
    team_logo_url: str | None
    position: str
    competition_name: str
    total_pts: float
    matches_played: int
    photo_url: str | None
    goals: int = 0
    assists: int = 0
    dribbles_won: int = 0
    duels_won: int = 0


@dataclass(frozen=True)
class PlayerEventDTO:
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


@dataclass(frozen=True)
class FixtureActionBreakdown:
    count: int
    pts: float


@dataclass(frozen=True)
class PlayerFixtureDTO:
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
    breakdown: dict[str, FixtureActionBreakdown] | None = None
    rating: float | None = None


@dataclass(frozen=True)
class PlayerSeasonStatsDTO:
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


@dataclass(frozen=True)
class CompetitionDTO:
    id: int
    name: str
    country: str
    factor: float


@dataclass(frozen=True)
class StandingEntryDTO:
    position: int
    team: str
    points: int


@dataclass(frozen=True)
class SystemCountsDTO:
    players: int
    scores: int
    competitions: int
    events: int
    latest_season: str | None


@dataclass(frozen=True)
class SeasonDTO:
    season: str
    is_latest: bool


# ─── Protocols (Ports) ───────────────────────────────────────────────

@runtime_checkable
class PlayerRepositoryProtocol(Protocol):
    async def get_by_id(self, player_id: int) -> PlayerDTO | None: ...
    async def exists(self, player_id: int) -> bool: ...


@runtime_checkable
class SFAScoreRepositoryProtocol(Protocol):
    async def get_best_score_for_player_season(
        self, player_id: int, season: str, rules_version_id: int | None = None,
    ) -> PlayerScoreDTO | None:
        """Score row con mayor total_pts para un jugador en una season."""
        ...

    async def get_global_rank(
        self, player_id: int, season: str, total_pts: float, rules_version_id: int | None = None,
    ) -> int:
        """Cantidad de jugadores con más pts + 1."""
        ...

    async def get_competitions_for_player_season(
        self, player_id: int, season: str, rules_version_id: int | None = None,
    ) -> list[str]:
        """Lista de nombres de competition donde el jugador tiene score."""
        ...

    async def get_ranking(
        self,
        season: str,
        position: str | None = None,
        competition_id: int | None = None,
        limit: int = 50,
        name: str | None = None,
        rules_version_id: int | None = None,
        use_total: bool = False,
    ) -> list[RankedPlayerDTO]: ...

    async def get_ranking_total(
        self,
        season: str,
        position: str | None = None,
        competition_id: int | None = None,
        name: str | None = None,
        rules_version_id: int | None = None,
    ) -> int:
        """Total de jugadores en el ranking (sin limit)."""
        ...

    async def latest_season(self) -> str | None: ...

    async def latest_season_for_player(self, player_id: int) -> str | None: ...

    async def get_total_player_stats(
        self, player_id: int, season: str, rules_version_id: int | None = None,
    ) -> tuple[int, int, int, float]:
        """Retorna (total_matches, total_goals, total_assists, total_pts) sumando todas las competiciones."""
        ...

    async def get_available_seasons_for_player(self, player_id: int) -> list[str]: ...

    async def get_ranking_all_seasons(
        self,
        position: str | None = None,
        competition_id: int | None = None,
        limit: int = 50,
        name: str | None = None,
        rules_version_id: int | None = None,
        use_total: bool = False,
    ) -> list[RankedPlayerDTO]: ...

    async def get_ranking_total_all_seasons(
        self,
        position: str | None = None,
        competition_id: int | None = None,
        name: str | None = None,
        rules_version_id: int | None = None,
    ) -> int: ...

    async def get_total_player_stats_all_seasons(
        self, player_id: int, rules_version_id: int | None = None,
    ) -> tuple[int, int, int, float]: ...

    async def get_global_rank_all_seasons(
        self, player_id: int, total_pts: float, rules_version_id: int | None = None,
    ) -> int: ...


@runtime_checkable
class SeasonRepositoryProtocol(Protocol):
    async def get_available_seasons(self) -> list[SeasonDTO]: ...


@runtime_checkable
class CompetitionRepositoryProtocol(Protocol):
    async def get_all(self) -> list[CompetitionDTO]: ...
    async def get_by_id(self, competition_id: int) -> CompetitionDTO | None: ...


@runtime_checkable
class StandingRepositoryProtocol(Protocol):
    async def get_standings(
        self,
        competition_id: int,
        season: str | None = None,
        matchday: int | None = None,
    ) -> tuple[str, str, int, list[StandingEntryDTO]]:
        """Retorna (competition_name, season, matchday, standings).

        Resuelve season/matchday al más reciente si son None.
        Lanza ValueError si no encuentra data.
        """
        ...


@runtime_checkable
class PlayerEventRepositoryProtocol(Protocol):
    async def get_events_by_player(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
    ) -> list[PlayerEventDTO]: ...

    async def get_fixtures_by_player(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
        competition_name: str | None = None,
        rival: str | None = None,
        date: date | None = None,
    ) -> list[PlayerFixtureDTO]: ...

    async def get_fixture_breakdown_by_player(
        self,
        player_id: int,
        fixture_ids: list[int],
    ) -> dict[int, dict[str, FixtureActionBreakdown]]: ...

    async def get_player_season_stats(
        self,
        player_id: int,
        competition_id: int | None,
        season: str | None,
    ) -> PlayerSeasonStatsDTO | None: ...


@runtime_checkable
class SystemRepositoryProtocol(Protocol):
    async def get_counts(self) -> SystemCountsDTO: ...
