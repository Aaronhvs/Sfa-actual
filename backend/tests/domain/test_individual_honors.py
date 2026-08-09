from __future__ import annotations

import pytest

from sfa.domain.individual_honors import (
    HonorCandidateStats,
    HonorScopeCategory,
    IndividualHonor,
    IndividualHonorType,
)


def test_candidate_rates_are_derived_from_totals() -> None:
    candidate = HonorCandidateStats(
        player_id=7,
        goals=4,
        assists=3,
        minutes=900,
        dribbles_won=30,
        dribbles_attempts=40,
        duels_won=50,
        duels_total=80,
    )

    assert candidate.dribble_rate == 0.75
    assert candidate.duel_rate == 0.625


def test_honor_rejects_awarded_points_above_raw_points() -> None:
    with pytest.raises(ValueError, match="Awarded honor points"):
        IndividualHonor(
            id=None,
            player_id=7,
            scope_key="season-2025",
            scope_label="2025/2026",
            context_key="overall",
            context_label="2025/2026",
            scope_category=HonorScopeCategory.AWARD_PERIOD,
            honor_type=IndividualHonorType.TOP_SCORER,
            source_season="2025",
            competition_id=None,
            rules_version_id=4,
            metric_value=30,
            metric_total=None,
            metric_rate=None,
            raw_bonus_pts=3000,
            awarded_bonus_pts=3001,
            calculation_details={},
        )


def test_rate_based_honor_requires_metric_total() -> None:
    with pytest.raises(ValueError, match="requires a metric total"):
        IndividualHonor(
            id=None,
            player_id=7,
            scope_key="season-2025",
            scope_label="2025/2026",
            context_key="overall",
            context_label="2025/2026",
            scope_category=HonorScopeCategory.AWARD_PERIOD,
            honor_type=IndividualHonorType.BEST_DRIBBLER,
            source_season="2025",
            competition_id=None,
            rules_version_id=4,
            metric_value=30,
            metric_total=None,
            metric_rate=0.75,
            raw_bonus_pts=1500,
            awarded_bonus_pts=1500,
            calculation_details={},
        )
