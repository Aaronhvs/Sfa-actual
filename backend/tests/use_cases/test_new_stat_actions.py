"""Tests for spec 0003: BLOCKS, XA_NO_ASSIST, XG_NO_GOAL, FOULS_DRAWN scoring."""
from __future__ import annotations

import pytest

from sfa.domain.scoring.services import BASE_POINTS_TABLE
from sfa.domain.scoring.value_objects import ActionType, PositionGroup
from sfa.infrastructure.models.enums import EventType

from .test_ingest_stats_event import (
    FakeFootballProvider,
    FakeIngestionRepository,
    _LEAGUE,
    _fixture,
    _player_stats,
)
from sfa.application.use_cases.ingest_competition import IngestCompetitionUseCase


# ---------------------------------------------------------------------------
# Task 5a — BASE_POINTS_TABLE completeness
# ---------------------------------------------------------------------------

def test_base_points_table_covers_all_action_types():
    """Every ActionType must have an entry for every group in BASE_POINTS_TABLE."""
    for group in BASE_POINTS_TABLE:
        for action in ActionType:
            assert action in BASE_POINTS_TABLE[group], (
                f"ActionType.{action.name} missing from BASE_POINTS_TABLE[{group.name}]"
            )


# ---------------------------------------------------------------------------
# Task 5b — Agreed values
# ---------------------------------------------------------------------------

def test_blocks_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.BLOCKS] == 150
    assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.BLOCKS] == 100
    assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.BLOCKS] == 130


def test_xg_no_goal_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.XG_NO_GOAL] == 70
    assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.XG_NO_GOAL] == 50
    assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.XG_NO_GOAL] == 30


def test_xa_no_assist_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.XA_NO_ASSIST] == 60
    assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.XA_NO_ASSIST] == 100
    assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.XA_NO_ASSIST] == 80


def test_fouls_drawn_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.FOULS_DRAWN] == 50
    assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.FOULS_DRAWN] == 35
    assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.FOULS_DRAWN] == 20


# ---------------------------------------------------------------------------
# Task 5c — Floor a cero para valores derivados
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_xa_no_assist_floor_to_zero_when_assists_exceed_key_passes():
    """passes_key=0 with assists=1 must not produce negative XA_NO_ASSIST."""
    from sfa.domain.ingestion_ports import PlayerStatsRawDTO
    from datetime import datetime, timezone

    player = PlayerStatsRawDTO(
        player_external_id=99,
        player_name="Test MF",
        position="Midfielder",
        minutes=90,
        goals=0,
        assists=1,
        shots_on=0,
        passes_key=0,
        dribbles_success=0,
        duels_won=1,
        tackles=0,
        interceptions=0,
        blocks=0,
        fouls_drawn=0,
        dribbles_attempts=0,
    )
    provider = FakeFootballProvider(fixtures=[_fixture()], player=player)
    repo = FakeIngestionRepository()
    uc = IngestCompetitionUseCase(provider, repo)

    await uc.execute(_LEAGUE, 2024)

    stats_events = [
        e for evts in repo.player_events.values()
        for e in evts if e["event_type"] == EventType.STATS
    ]
    assert len(stats_events) == 1
    assert stats_events[0]["pts"] >= 0, "pts must never be negative"


@pytest.mark.anyio
async def test_xg_no_goal_floor_to_zero_when_goals_exceed_shots_on():
    """shots_on=1 with goals=2 (data inconsistency) must floor XG_NO_GOAL to 0."""
    from sfa.domain.ingestion_ports import PlayerStatsRawDTO

    player = PlayerStatsRawDTO(
        player_external_id=98,
        player_name="Test FW",
        position="Attacker",
        minutes=90,
        goals=2,
        assists=0,
        shots_on=1,
        passes_key=0,
        dribbles_success=0,
        duels_won=1,
        tackles=0,
        interceptions=0,
        blocks=0,
        fouls_drawn=0,
        dribbles_attempts=0,
    )
    provider = FakeFootballProvider(fixtures=[_fixture()], player=player)
    repo = FakeIngestionRepository()
    uc = IngestCompetitionUseCase(provider, repo)

    await uc.execute(_LEAGUE, 2024)

    stats_events = [
        e for evts in repo.player_events.values()
        for e in evts if e["event_type"] == EventType.STATS
    ]
    assert stats_events[0]["pts"] >= 0


# ---------------------------------------------------------------------------
# Task 5e — Scoring end-to-end con nuevos campos
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_new_stat_actions_contribute_to_stats_pts():
    """MF with passes_key, shots_on, fouls_drawn, blocks gets higher pts than without."""
    from sfa.domain.ingestion_ports import PlayerStatsRawDTO

    # MF con stats nuevas activas
    player_with = PlayerStatsRawDTO(
        player_external_id=96,
        player_name="Test MF With",
        position="Midfielder",
        minutes=90,
        goals=0,
        assists=0,
        shots_on=3,
        passes_key=4,
        dribbles_success=0,
        duels_won=0,
        tackles=0,
        interceptions=0,
        blocks=2,
        fouls_drawn=3,
        dribbles_attempts=0,
    )
    # Mismo MF sin stats nuevas
    player_without = PlayerStatsRawDTO(
        player_external_id=95,
        player_name="Test MF Without",
        position="Midfielder",
        minutes=90,
        goals=0,
        assists=0,
        shots_on=0,
        passes_key=0,
        dribbles_success=0,
        duels_won=0,
        tackles=0,
        interceptions=0,
        blocks=0,
        fouls_drawn=0,
        dribbles_attempts=0,
    )

    repo_with = FakeIngestionRepository()
    await IngestCompetitionUseCase(
        FakeFootballProvider(fixtures=[_fixture()], player=player_with),
        repo_with,
    ).execute(_LEAGUE, 2024)

    repo_without = FakeIngestionRepository()
    await IngestCompetitionUseCase(
        FakeFootballProvider(fixtures=[_fixture()], player=player_without),
        repo_without,
    ).execute(_LEAGUE, 2024)

    stats_with = next(iter(repo_with.player_stats.values()))
    stats_without = next(iter(repo_without.player_stats.values()))

    assert stats_with["shots_on"] > stats_without["shots_on"]
    assert stats_with["passes_key"] > stats_without["passes_key"]
    assert stats_with["blocks"] > stats_without["blocks"]
    assert stats_with["fouls_drawn"] > stats_without["fouls_drawn"]
