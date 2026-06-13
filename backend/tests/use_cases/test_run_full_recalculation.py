from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.run_full_recalculation import RunFullRecalculationUseCase
from sfa.domain.scoring.entities import CompetitionAchievement, ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from tests.use_cases.test_calculate_scores_for_rules_version import (
    FakePlayerEventScoreRepository,
    FakeScoringRulesVersionRepository,
    _make_goal_event,
)
from tests.use_cases.test_scoring_balance_v2 import FakeCompetitionAchievementRepository


def _make_version() -> ScoringRulesVersion:
    return ScoringRulesVersion(
        id=3,
        name="v2",
        version="2.0",
        description="",
        is_active=True,
        config=ScoringConfig.default_v2(),
        created_at=datetime.now(timezone.utc),
    )


def _make_achievement(competition_id: int) -> CompetitionAchievement:
    return CompetitionAchievement(
        id=competition_id,
        competition_id=competition_id,
        team_id=1,
        season="2024",
        phase="winner",
        bonus_points=1000,
        weight=1.0,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.anyio
async def test_full_recalculation_scores_events_and_calculates_bonuses():
    event_repo = FakePlayerEventScoreRepository(events=[_make_goal_event()])
    achievement_repo = FakeCompetitionAchievementRepository(
        achievements=[_make_achievement(1), _make_achievement(2)],
        team_minutes=900,
        player_minutes=450,
        player_ids=[10],
        rank_in_team=1,
        avg_rating=8.0,
    )
    use_case = RunFullRecalculationUseCase(
        rules_version_repo=FakeScoringRulesVersionRepository(_make_version()),
        event_score_repo=event_repo,
        achievement_repo=achievement_repo,
    )

    result = await use_case.execute(
        rules_version_id=3,
        season="2024",
        force_recalculate=True,
    )

    assert result.status == "completed"
    assert result.events_calculated == 1
    assert result.players_updated == 1
    assert result.competitions_with_bonuses == 2
    assert result.achievement_bonuses_created == 2
    assert len(event_repo.bulk_rebuild_calls) == 1
    assert len(achievement_repo.upserted_bonuses) == 2


@pytest.mark.anyio
async def test_full_recalculation_returns_failed_when_rules_version_missing():
    use_case = RunFullRecalculationUseCase(
        rules_version_repo=FakeScoringRulesVersionRepository(None),
        event_score_repo=FakePlayerEventScoreRepository(events=[_make_goal_event()]),
        achievement_repo=FakeCompetitionAchievementRepository(),
    )

    result = await use_case.execute(
        rules_version_id=999,
        season="2024",
        force_recalculate=True,
    )

    assert result.status == "failed"
    assert result.events_calculated == 0
    assert result.achievement_bonuses_created == 0
