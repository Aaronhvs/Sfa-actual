from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from sfa.infrastructure.models.enums import EventType, IngestionStatus, Position


@dataclass(frozen=True)
class StandingRawDTO:
    team_external_id: int
    team_name: str
    position: int
    points: int
    played: int


@dataclass(frozen=True)
class FixtureRawDTO:
    external_id: int
    home_team_external_id: int
    away_team_external_id: int
    home_team_name: str
    away_team_name: str
    round_str: str
    league_name: str
    played_at: datetime
    home_goals: int
    away_goals: int


@dataclass(frozen=True)
class FixtureEventRawDTO:
    type: str
    detail: str
    player_name: str
    assist_name: str | None
    team_external_id: int
    minute: int
    extra_minute: int
    source_sequence: int | None = None


@dataclass(frozen=True)
class PlayerStatsRawDTO:
    player_external_id: int
    player_name: str
    position: str
    minutes: int
    goals: int
    assists: int
    shots_on: int
    passes_key: int
    dribbles_success: int
    duels_won: int
    tackles: int
    interceptions: int
    blocks: int
    fouls_drawn: int = 0
    dribbles_attempts: int = 0
    shots_total: int = 0
    passes_total: int = 0
    passes_accuracy: int = 0
    dribbles_past: int = 0
    duels_total: int = 0
    fouls_committed: int = 0
    cards_yellow: int = 0
    cards_red: int = 0
    penalty_won: int = 0
    saves: int = 0
    goals_conceded: int = 0
    photo_url: str | None = None
    rating: float | None = None


@dataclass(frozen=True)
class FixtureInfoRow:
    fixture_id: int
    fixture_external_id: int
    season: str


@dataclass(frozen=True)
class PlayerFixtureInfoRow:
    fixture_id: int
    fixture_external_id: int
    season: str
    competition_id: int
    home_team_id: int
    away_team_id: int
    player_team_id: int
    player_external_id: int
    player_name: str
    stage: str
    home_team_external_id: int | None = None
    away_team_external_id: int | None = None
    player_team_external_id: int | None = None


@dataclass(frozen=True)
class IngestionLogRow:
    competition_id: int
    competition_name: str
    season: str
    status: IngestionStatus
    started_at: datetime
    finished_at: datetime | None
    error_msg: str | None


@dataclass(frozen=True)
class CompetitionIngestionStatusDTO:
    competition_name: str
    league_id: int
    season: str
    status: str
    fixtures_in_db: int
    last_ingested_at: datetime | None
    error_msg: str | None


@runtime_checkable
class FootballDataProviderPort(Protocol):
    async def fetch_standings(
        self, league_id: int, season: int,
    ) -> list[StandingRawDTO]: ...

    async def fetch_team_fixtures(
        self, team_id: int, league_id: int, season: int,
    ) -> list[FixtureRawDTO]: ...

    async def fetch_fixture_events(
        self, fixture_id: int,
    ) -> list[FixtureEventRawDTO]: ...

    async def fetch_fixture_players(
        self, fixture_id: int, team_id: int,
    ) -> list[PlayerStatsRawDTO]: ...

    async def fetch_all_fixture_players(
        self, fixture_external_id: int,
    ) -> list[PlayerStatsRawDTO]: ...


@runtime_checkable
class IngestionRepositoryPort(Protocol):
    async def upsert_competition(
        self, name: str, country: str, factor: float,
        participant_kind: str = "club",
    ) -> int: ...

    async def upsert_team(
        self, external_id: int, name: str, competition_id: int,
    ) -> int: ...

    async def upsert_player(
        self, external_id: int, name: str, position: Position,
        photo_url: str | None = None,
        update_position: bool = True,
        position_source: str = "apifootball",
    ) -> int: ...

    async def upsert_fixture(
        self, external_id: int, competition_id: int,
        home_team_id: int, away_team_id: int,
        stage: str, season: str, played_at: datetime,
        matchday: int | None,
    ) -> int: ...

    async def upsert_standing_snapshot(
        self, competition_id: int, team_id: int,
        season: str, matchday: int, position: int, points: int,
    ) -> None: ...

    async def upsert_player_event(
        self, player_id: int, fixture_id: int, team_id: int,
        minute: int, event_type: EventType,
        score_before: str | None, score_diff: int | None,
        psxg: float | None,
        m1: float, m2: float, m3: float, m4: float,
        mvisit: float, pts: float,
        player_team_pos: int | None = None,
        rival_team_pos: int | None = None,
        is_away: bool | None = None,
    ) -> None: ...

    async def upsert_player_stats(
        self, player_id: int, fixture_id: int, team_id: int,
        season: str, stats: dict,
    ) -> None: ...

    async def upsert_season_score(
        self, player_id: int, competition_id: int,
        season: str, total_pts: float,
        matches_played: int, breakdown: dict, team_id: int | None = None,
    ) -> None: ...

    async def get_stage_factor(
        self, competition_id: int, stage: str,
    ) -> float: ...

    async def save_ingestion_log(
        self, competition_id: int, season: str,
        status: IngestionStatus, players_processed: int | None,
        error_msg: str | None,
    ) -> None: ...

    async def delete_player_events_for_fixture(
        self, player_id: int, fixture_id: int,
    ) -> None: ...

    async def get_season_fixtures(
        self, competition_id: int, season: str,
    ) -> list[FixtureInfoRow]: ...

    async def get_player_id_by_external(
        self, external_id: int,
    ) -> int | None: ...

    async def get_last_ingestion_log(
        self, competition_id: int, season: str,
    ) -> IngestionLogRow | None: ...

    async def get_ingestion_logs_by_season(
        self, season: str,
    ) -> list[IngestionLogRow]: ...

    async def get_fixture_counts_by_competition(
        self, season: str,
    ) -> dict[int, int]: ...

    async def get_fixtures_for_player(
        self,
        player_id: int,
        season: str,
        competition_id: int | None = None,
    ) -> list[PlayerFixtureInfoRow]: ...


@dataclass(frozen=True)
class PlayerSeasonScoreRow:
    player_id: int
    total_pts: float
    matches_played: int
    breakdown: dict
    total_minutes: int


@runtime_checkable
class ScoringRepositoryPort(Protocol):
    async def get_competition_ids_with_season(self, season: str) -> list[int]: ...

    async def get_player_scores_for_competition(
        self, competition_id: int, season: str,
    ) -> list[PlayerSeasonScoreRow]: ...

    async def upsert_season_score(
        self, player_id: int, competition_id: int,
        season: str, total_pts: float,
        matches_played: int, breakdown: dict,
        rules_version_id: int | None = None,
        team_id: int | None = None,
    ) -> None: ...
