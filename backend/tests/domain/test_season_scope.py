import pytest

from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource


def test_award_period_accepts_club_and_world_cup_sources():
    scope = AwardPeriodScope(
        key="season-2025",
        label="2025/2026",
        kind=ScopeKind.AWARD_PERIOD,
        sources=(ScoreSource("2025", (1, 2)), ScoreSource("2026", (350,))),
        is_latest=True,
        includes_world_cup=True,
    )

    assert scope.pairs == frozenset({("2025", 1), ("2025", 2), ("2026", 350)})


def test_score_source_normalizes_competition_ids():
    source = ScoreSource("2025", (2, 1, 2))

    assert source.competition_ids == (1, 2)


def test_scope_rejects_overlapping_sources():
    with pytest.raises(ValueError, match="cannot overlap"):
        AwardPeriodScope(
            key="season-2025",
            label="2025/2026",
            kind=ScopeKind.AWARD_PERIOD,
            sources=(ScoreSource("2025", (1,)), ScoreSource("2025", (1, 2))),
        )


def test_tournament_requires_one_physical_competition():
    with pytest.raises(ValueError, match="exactly one competition"):
        AwardPeriodScope(
            key="world-cup-2026",
            label="Mundial 2026",
            kind=ScopeKind.TOURNAMENT,
            sources=(ScoreSource("2026", (350, 351)),),
        )
