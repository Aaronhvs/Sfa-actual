from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Raw DTOs — scraped data from external sources
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FBrefPlayerStatsDTO:
    player_name: str
    team_name: str
    position: str           # "FW", "MF", "DF", "GK"
    minutes: int
    goals: int
    assists: int
    xg: float
    xa: float
    progressive_passes: int
    progressive_carries: int
    psxg_total: float | None    # PSxG total for the season (Shooting table)


@dataclass(frozen=True)
class UnderstatPlayerDTO:
    player_name: str
    team_name: str
    understat_id: str
    goals: int
    assists: int
    npg: int                # non-penalty goals
    npxg: float             # non-penalty xG
    xa: float
    shots: int
    key_passes: int
    xg_per_shot: float      # proxy for PSxG per shot
    minutes: int
    games: int


# ---------------------------------------------------------------------------
# Internal row DTOs — DB-sourced data for use-case logic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlayerEnrichDTO:
    id: int
    name: str
    external_id: int | None
    fbref_id: str | None
    understat_id: int | None


@dataclass(frozen=True)
class PlayerEventRow:
    id: int
    event_type: str
    minute: int
    m1: float
    m2: float
    m3: float
    mvisit: float


@dataclass(frozen=True)
class PlayerEventRecalcRow:
    id: int
    player_id: int
    player_position: str    # Position enum value (e.g. "DEL", "MC", "DC")
    event_type: str
    fixture_id: int
    m1: float
    m2: float
    m3: float
    mvisit: float
    psxg: float
    current_pts: float


@dataclass(frozen=True)
class PlayerStatsEventRecalcRow:
    event_id: int
    player_id: int
    player_position: str
    m1: float
    m2: float
    current_pts: float
    duels_won: int
    tackles_won: int
    interceptions: int
    blocks: int
    dribbles_won: int
    passes_key: int
    passes_total: int
    passes_accuracy: int
    shots_on: int
    shots_total: int
    dribbles_past: int
    duels_total: int
    fouls_drawn: int
    fouls_committed: int
    cards_yellow: int
    cards_red: int
    penalty_won: int
    goals: int
    assists: int
    rating: float | None


@dataclass(frozen=True)
class PlayerSeasonEventRow:
    id: int
    player_id: int
    fixture_id: int
    event_type: str
    pts: float


@dataclass(frozen=True)
class SeasonScoreRow:
    player_id: int
    competition_id: int
    season: str
    total_pts: float
    matches_played: int
    breakdown: dict


# ---------------------------------------------------------------------------
# Result DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnrichmentResult:
    competition: str
    players_matched: int
    players_skipped: int
    events_enriched: int    # events with PSxG updated
    stats_enriched: int     # player_stats rows updated with FBref fields
    status: str             # "completed" | "failed"
    error: str | None


@dataclass(frozen=True)
class RecalculationResult:
    events_updated: int
    scores_updated: int


# ---------------------------------------------------------------------------
# Ports (Protocols)
# ---------------------------------------------------------------------------


@runtime_checkable
class FBrefProviderPort(Protocol):
    async def fetch_league_player_stats(
        self, league: str,
    ) -> list[FBrefPlayerStatsDTO]: ...
    # Returns standard stats (xG, xA, PrgP, PrgC) + PSxG from Shooting table


@runtime_checkable
class UnderstatProviderPort(Protocol):
    async def fetch_league_players(
        self, league: str, season: int,
    ) -> list[UnderstatPlayerDTO]: ...
    # Returns xG, xA, shots, key_passes, xg_per_shot derived


@runtime_checkable
class EnrichmentRepositoryPort(Protocol):
    async def get_players_by_competition(
        self, competition_id: int, season: str,
    ) -> list[PlayerEnrichDTO]: ...

    async def get_player_events_without_psxg(
        self, player_id: int, competition_id: int, season: str,
    ) -> list[PlayerEventRow]: ...

    async def update_player_external_ids(
        self, player_id: int,
        fbref_id: str | None,
        understat_id: int | None,
    ) -> None: ...

    async def update_player_stats_from_fbref(
        self, player_id: int, season: str, stats: dict,
    ) -> None: ...

    async def update_event_psxg(
        self, event_id: int, psxg: float,
    ) -> None: ...

    async def update_event_scores(
        self, event_id: int, m4: float, pts: float,
    ) -> None: ...

    async def update_season_score(
        self, player_id: int, competition_id: int,
        season: str, total_pts: float,
        matches_played: int, breakdown: dict,
    ) -> None: ...

    async def get_events_with_psxg_for_recalc(
        self, competition_id: int, season: str,
    ) -> list[PlayerEventRecalcRow]: ...

    async def get_stats_events_for_recalc(
        self, competition_id: int, season: str,
    ) -> list[PlayerStatsEventRecalcRow]: ...

    async def update_event_pts(self, event_id: int, pts: float, m2: float | None = None) -> None: ...

    async def get_all_player_season_events(
        self, player_id: int, competition_id: int, season: str,
    ) -> list[PlayerSeasonEventRow]: ...

    async def get_player_season_score_row(
        self, player_id: int, competition_id: int, season: str,
    ) -> SeasonScoreRow | None: ...

    async def get_player_season_real_stats(
        self, player_id: int, competition_id: int, season: str,
    ) -> tuple[int, int]: ...
