from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from sfa.domain.scoring.entities import (
    CompetitionAchievement,
    PlayerAchievementBonus,
    PlayerEventScore,
    ScoringRulesVersion,
)
from sfa.domain.scoring.value_objects import ScoringConfig


@dataclass(frozen=True)
class PlayerEventRawContextDTO:
    """All raw data needed to (re)score a single PlayerEvent under any rules version."""

    event_id: int
    player_id: int
    fixture_id: int
    competition_id: int
    season: str
    event_type: str        # EventType value string
    minute: int
    score_diff: int | None
    psxg: float | None
    player_team_pos: int | None
    rival_team_pos: int | None
    is_away: bool | None
    stage_factor: float
    # Stats fields (from player_stats) — populated for STATS events, None otherwise
    goals: int | None
    assists: int | None
    shots_on: int | None
    passes_key: int | None
    passes_total: int | None
    passes_accuracy: float | None
    dribbles_won: int | None
    duels_won: int | None
    tackles_won: int | None
    interceptions: int | None
    blocks: int | None
    fouls_drawn: int | None
    fouls_committed: int | None
    cards_yellow: int | None
    cards_red: int | None
    penalty_won: int | None
    dribbles_past: int | None
    rating: float | None
    player_position: str | None    # Position value string
    # v2 fields: minutes played in the match + pre-computed team strengths
    minutes: int | None
    player_team_strength: float | None
    rival_team_strength: float | None
    # B1 fields (spec 0034): populated when birth_date is available in DB
    player_birth_date: date | None = None
    fixture_date: date | None = None


@dataclass(frozen=True)
class TeamStandingRow:
    """Aggregated standing data for one team in one competition-season."""

    team_id: int
    season: str
    competition_id: int
    avg_position: float
    total_points: int
    matchdays_played: int


@dataclass(frozen=True)
class TeamEloRow:
    team_id: int
    season: str
    elo_raw: float
    strength: float


@dataclass(frozen=True)
class NationalTeamEloEntry:
    country_name: str
    elo_raw: float
    rank: int | None
    source_date: str | None


@dataclass(frozen=True)
class TeamCompetitionRow:
    team_id: int
    team_name: str
    competition_id: int


@dataclass(frozen=True)
class TeamStrengthCoverageRow:
    team_id: int
    team_name: str
    competition_id: int
    strength: float | None
    elo_raw: float | None
    source: str | None


@dataclass(frozen=True)
class FixtureEloRow:
    fixture_id: int
    home_team_id: int
    away_team_id: int
    played_at: datetime
    competition_id: int
    home_goals: int
    away_goals: int
    season: str


@dataclass(frozen=True)
class PlayerCompetitionAchievementDTO:
    achievement_id: int
    competition_id: int
    competition_name: str
    team_id: int
    team_name: str
    season: str
    phase: str
    title_count: int
    bonus_pts: float


@runtime_checkable
class ScoringRulesVersionRepositoryPort(Protocol):
    async def get_active_version(self) -> ScoringRulesVersion | None: ...

    async def get_version_by_id(self, version_id: int) -> ScoringRulesVersion | None: ...

    async def list_versions(self) -> list[ScoringRulesVersion]: ...

    async def save_version(
        self,
        name: str,
        version: str,
        description: str,
        config: ScoringConfig,
    ) -> int: ...

    async def set_active_version(self, version_id: int) -> None: ...


@runtime_checkable
class PlayerEventScoreRepositoryPort(Protocol):
    async def get_events_for_recalc(
        self,
        season: str,
        competition_id: int | None,
        match_id: int | None,
        player_id: int | None,
    ) -> list[PlayerEventRawContextDTO]: ...

    async def upsert_event_score(self, score: PlayerEventScore) -> None: ...

    async def event_score_exists(
        self, event_id: int, rules_version_id: int
    ) -> bool: ...

    async def delete_event_scores_for_version(
        self,
        rules_version_id: int,
        season: str,
        competition_id: int | None,
    ) -> None: ...

    async def get_player_event_totals_for_season(
        self,
        player_id: int,
        season: str,
        competition_id: int,
        rules_version_id: int,
    ) -> tuple[float, int]: ...

    async def get_players_with_events_in_scope(
        self,
        season: str,
        competition_id: int | None,
        rules_version_id: int,
    ) -> list[int]: ...

    async def get_season_score_breakdown(
        self,
        player_id: int,
        season: str,
        competition_id: int,
        rules_version_id: int,
    ) -> dict: ...

    async def get_competition_name_map(self) -> dict[int, str]: ...

    async def bulk_rebuild_season_scores(
        self,
        rules_version_id: int,
        season: str,
        competition_id: int | None = None,
    ) -> int:
        """Rebuild sfa_season_scores for all (player, competition) pairs in scope."""
        ...


@runtime_checkable
class TeamStrengthRepositoryPort(Protocol):
    async def get_team_strength(
        self, team_id: int, season: str, competition_id: int
    ) -> float | None: ...

    async def upsert_team_strength(
        self,
        team_id: int,
        season: str,
        competition_id: int,
        strength: float,
        source: str,
    ) -> None: ...

    async def get_team_standings_for_season(
        self, competition_id: int, season: str
    ) -> list[TeamStandingRow]: ...

    async def get_team_strength_with_elo(
        self, team_id: int, season: str, competition_id: int
    ) -> tuple[float | None, float | None]: ...

    async def upsert_team_elo(
        self,
        team_id: int,
        season: str,
        elo_raw: float,
        strength_normalized: float,
        source: str,
        competition_ids: list[int],
    ) -> None: ...

    async def get_all_teams_with_elo(self, season: str) -> list[TeamEloRow]: ...

    async def get_fixtures_for_elo_recalc(
        self, season: str, competition_ids: list[int]
    ) -> list[FixtureEloRow]: ...

    async def get_team_name_id_map(self, season: str) -> dict[str, int]: ...

    async def get_active_competition_ids_for_team(
        self, team_id: int, season: str
    ) -> list[int]: ...

    async def get_competition_id_by_name(self, name: str) -> int | None: ...

    async def get_teams_for_competition_season(
        self, competition_id: int, season: str
    ) -> list[TeamCompetitionRow]: ...

    async def get_team_strength_coverage(
        self, competition_id: int, season: str
    ) -> list[TeamStrengthCoverageRow]: ...


@runtime_checkable
class CompetitionAchievementRepositoryPort(Protocol):
    async def upsert_achievement(self, achievement: CompetitionAchievement) -> int: ...

    async def get_achievements_for_season(
        self, competition_id: int, season: str
    ) -> list[CompetitionAchievement]: ...

    async def upsert_player_bonus(self, bonus: PlayerAchievementBonus) -> None: ...

    async def get_team_total_minutes(
        self, team_id: int, competition_id: int, season: str
    ) -> int: ...

    async def get_player_minutes_in_competition(
        self, player_id: int, competition_id: int, season: str
    ) -> int: ...

    async def get_players_for_team_season(
        self, team_id: int, competition_id: int, season: str
    ) -> list[int]: ...

    async def update_season_score_bonus(
        self,
        player_id: int,
        competition_id: int,
        season: str,
        rules_version_id: int,
        bonus_pts: float,
    ) -> None: ...

    async def get_player_rank_in_team(
        self,
        player_id: int,
        team_id: int,
        competition_id: int,
        season: str,
        rules_version_id: int,
    ) -> int: ...

    async def get_player_avg_rating(
        self,
        player_id: int,
        competition_id: int,
        season: str,
    ) -> float | None: ...

    async def get_competition_ids_for_season(self, season: str) -> list[int]: ...

    async def get_achievements_for_domestic_leagues(
        self, season: str, league_names: list[str]
    ) -> list[tuple[CompetitionAchievement, str]]: ...

    async def get_player_achievements(
        self,
        player_id: int,
        rules_version_id: int,
        season: str | None = None,
    ) -> list[PlayerCompetitionAchievementDTO]: ...
