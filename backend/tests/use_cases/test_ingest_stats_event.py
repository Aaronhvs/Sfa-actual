"""Tests for spec 0002: STATS player_event persisted per player per fixture."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.ingest_competition import IngestCompetitionUseCase, LeagueConfig
from sfa.domain.ingestion_ports import (
    FixtureEventRawDTO,
    FixtureRawDTO,
    PlayerStatsRawDTO,
    StandingRawDTO,
)
from sfa.domain.scoring.services import SFAScoringService
from sfa.infrastructure.models.enums import EventType, IngestionStatus, Position

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLAYED_AT = datetime(2024, 9, 14, 17, 0, tzinfo=timezone.utc)
_LEAGUE = LeagueConfig(id=1, name="Test League", country="TST", comp_factor=1.0, top_n=1)


def _player_stats(
    external_id: int = 42,
    name: str = "Test Player",
    position: str = "Attacker",
    minutes: int = 90,
    dribbles_success: int = 3,
    duels_won: int = 2,
    tackles: int = 1,
) -> PlayerStatsRawDTO:
    return PlayerStatsRawDTO(
        player_external_id=external_id,
        player_name=name,
        position=position,
        minutes=minutes,
        goals=0,
        assists=0,
        shots_on=0,
        passes_key=0,
        dribbles_success=dribbles_success,
        duels_won=duels_won,
        tackles=tackles,
        interceptions=0,
        blocks=0,
    )


def _fixture(ext_id: int = 9001, home_team: int = 1, away_team: int = 2) -> FixtureRawDTO:
    return FixtureRawDTO(
        external_id=ext_id,
        home_team_external_id=home_team,
        away_team_external_id=away_team,
        home_team_name="Home FC",
        away_team_name="Away FC",
        round_str="Regular Season - 1",
        league_name="Test League",
        played_at=_PLAYED_AT,
        home_goals=0,
        away_goals=0,
    )


# ---------------------------------------------------------------------------
# Fake provider
# ---------------------------------------------------------------------------

class FakeFootballProvider:
    """Returns deterministic data; fixtures only for team_id=1."""

    def __init__(self, fixtures: list[FixtureRawDTO], player: PlayerStatsRawDTO):
        self._fixtures = fixtures
        self._player = player

    async def fetch_standings(self, league_id: int, season: int) -> list[StandingRawDTO]:
        return [StandingRawDTO(
            team_external_id=1,
            team_name="Home FC",
            position=5,
            points=30,
            played=10,
        )]

    async def fetch_team_fixtures(
        self, team_id: int, league_id: int, season: int,
    ) -> list[FixtureRawDTO]:
        return self._fixtures if team_id == 1 else []

    async def fetch_fixture_events(self, fixture_id: int) -> list[FixtureEventRawDTO]:
        return []

    async def fetch_fixture_players(
        self, fixture_id: int, team_id: int,
    ) -> list[PlayerStatsRawDTO]:
        return [self._player] if team_id == 1 else []

    def get_stage(self, round_str: str, league_name: str) -> str:
        return "regular"


# ---------------------------------------------------------------------------
# Fake repository
# ---------------------------------------------------------------------------

class FakeIngestionRepository:
    """Full Fake (no MagicMock) implementing IngestionRepositoryPort."""

    def __init__(self) -> None:
        self._comp_counter = 0
        self._team_counter = 0
        self._player_counter = 0
        self._fixture_counter = 0
        self._team_ids: dict[int, int] = {}
        self._player_ids: dict[int, int] = {}
        self._fixture_ids: dict[int, int] = {}
        # player_events keyed by (player_id, fixture_id) → list of event dicts
        self.player_events: dict[tuple[int, int], list[dict]] = {}
        # latest upsert_season_score call per player_id
        self.season_scores: dict[int, dict] = {}

    async def upsert_competition(self, name: str, country: str, factor: float) -> int:
        self._comp_counter += 1
        return self._comp_counter

    async def upsert_team(
        self, external_id: int, name: str, competition_id: int,
    ) -> int:
        if external_id not in self._team_ids:
            self._team_counter += 1
            self._team_ids[external_id] = self._team_counter
        return self._team_ids[external_id]

    async def upsert_player(
        self, external_id: int, name: str, team_id: int, position: Position,
        photo_url: str | None = None,
        update_position: bool = True,
        position_source: str = "apifootball",
    ) -> int:
        if external_id not in self._player_ids:
            self._player_counter += 1
            self._player_ids[external_id] = self._player_counter
        return self._player_ids[external_id]

    async def upsert_fixture(
        self,
        external_id: int,
        competition_id: int,
        home_team_id: int,
        away_team_id: int,
        stage: str,
        season: str,
        played_at: datetime,
        matchday: int | None,
    ) -> int:
        if external_id not in self._fixture_ids:
            self._fixture_counter += 1
            self._fixture_ids[external_id] = self._fixture_counter
        return self._fixture_ids[external_id]

    async def upsert_standing_snapshot(
        self,
        competition_id: int,
        team_id: int,
        season: str,
        matchday: int,
        position: int,
        points: int,
    ) -> None:
        pass

    async def upsert_player_stats(
        self, player_id: int, fixture_id: int, season: str, stats: dict,
    ) -> None:
        pass

    async def upsert_player_event(
        self,
        player_id: int,
        fixture_id: int,
        minute: int,
        event_type: EventType,
        score_before: str | None,
        score_diff: int | None,
        psxg: float | None,
        m1: float,
        m2: float,
        m3: float,
        m4: float,
        mvisit: float,
        pts: float,
        player_team_pos: int | None = None,
        rival_team_pos: int | None = None,
        is_away: bool | None = None,
    ) -> None:
        key = (player_id, fixture_id)
        self.player_events.setdefault(key, []).append({
            "event_type": event_type,
            "pts": pts,
            "minute": minute,
        })

    async def delete_player_events_for_fixture(
        self, player_id: int, fixture_id: int,
    ) -> None:
        self.player_events[(player_id, fixture_id)] = []

    async def upsert_season_score(
        self,
        player_id: int,
        competition_id: int,
        season: str,
        total_pts: float,
        matches_played: int,
        breakdown: dict,
    ) -> None:
        self.season_scores[player_id] = {
            "total_pts": total_pts,
            "matches_played": matches_played,
        }

    async def get_stage_factor(self, competition_id: int, stage: str) -> float:
        return 1.0

    async def save_ingestion_log(
        self,
        competition_id: int,
        season: str,
        status: IngestionStatus,
        players_processed: int | None,
        error_msg: str | None,
    ) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_player_without_goal_gets_stats_event():
    """A player with no goals/assists still gets a STATS player_event with pts > 0."""
    player = _player_stats(dribbles_success=3, duels_won=2, tackles=1)
    provider = FakeFootballProvider(fixtures=[_fixture()], player=player)
    repo = FakeIngestionRepository()
    uc = IngestCompetitionUseCase(provider, repo, SFAScoringService())

    await uc.execute(_LEAGUE, 2024)

    stats_events = [
        e
        for evts in repo.player_events.values()
        for e in evts
        if e["event_type"] == EventType.STATS
    ]
    assert len(stats_events) == 1, f"Expected 1 STATS event, got {len(stats_events)}"
    assert stats_events[0]["pts"] > 0, "STATS event pts should be > 0"


@pytest.mark.anyio
async def test_stats_event_not_duplicated_on_second_run():
    """Running the use case twice for the same fixture results in exactly 1 STATS row."""
    player = _player_stats(dribbles_success=3, duels_won=2, tackles=1)
    provider = FakeFootballProvider(fixtures=[_fixture()], player=player)
    repo = FakeIngestionRepository()
    uc = IngestCompetitionUseCase(provider, repo, SFAScoringService())

    await uc.execute(_LEAGUE, 2024)
    await uc.execute(_LEAGUE, 2024)

    stats_events = [
        e
        for evts in repo.player_events.values()
        for e in evts
        if e["event_type"] == EventType.STATS
    ]
    assert len(stats_events) == 1, (
        f"Expected 1 STATS event after 2 runs (idempotent), got {len(stats_events)}"
    )


@pytest.mark.anyio
async def test_stats_events_created_for_all_fixtures():
    """Ingestion creates a STATS player_event for each fixture the player appeared in."""
    player = _player_stats(dribbles_success=3, duels_won=2, tackles=1)
    fixtures = [
        _fixture(ext_id=9001, home_team=1, away_team=2),
        _fixture(ext_id=9002, home_team=1, away_team=3),
    ]
    provider = FakeFootballProvider(fixtures=fixtures, player=player)
    repo = FakeIngestionRepository()
    uc = IngestCompetitionUseCase(provider, repo, SFAScoringService())

    await uc.execute(_LEAGUE, 2024)

    # Ingestion no longer writes sfa_season_scores (that belongs to CalculateCompetitionScoresUseCase).
    # It must write one STATS player_event per fixture.
    stats_events = [
        e
        for evts in repo.player_events.values()
        for e in evts
        if e["event_type"] == EventType.STATS
    ]
    assert len(stats_events) == 2, (
        f"Expected 2 STATS events (one per fixture), got {len(stats_events)}"
    )
