"""Tests for spec 0006: MratingFactor value object and rating-based stats multiplier."""
from __future__ import annotations

import pytest

from sfa.application.use_cases.recalculate_scores import RecalculateScoresUseCase
from sfa.domain.enrichment_ports import (
    PlayerSeasonEventRow,
    PlayerStatsEventRecalcRow,
    SeasonScoreRow,
)
from sfa.domain.scoring.services import SFAScoringService
from sfa.domain.scoring.value_objects import ActionType, MratingFactor, PositionGroup

# ---------------------------------------------------------------------------
# MratingFactor — todos los tramos y valores de borde
# ---------------------------------------------------------------------------

def test_mrating_none_yields_half():
    assert MratingFactor(None).value == 0.5


def test_mrating_below_7_yields_03():
    assert MratingFactor(6.9).value == 0.3
    assert MratingFactor(5.0).value == 0.3
    assert MratingFactor(0.0).value == 0.3


def test_mrating_exactly_7_yields_half():
    """7.0 is the lower bound of [7.0, 8.0) — should return 0.5."""
    assert MratingFactor(7.0).value == 0.5


def test_mrating_7_to_8_range_yields_half():
    assert MratingFactor(7.5).value == 0.5
    assert MratingFactor(7.99).value == 0.5


def test_mrating_exactly_8_yields_075():
    """8.0 is the lower bound of [8.0, 8.5) — should return 0.75."""
    assert MratingFactor(8.0).value == 0.75


def test_mrating_8_to_85_range_yields_075():
    assert MratingFactor(8.3).value == 0.75
    assert MratingFactor(8.49).value == 0.75


def test_mrating_exactly_85_yields_1():
    """8.5 is the lower bound of [8.5, ∞) — should return 1.0."""
    assert MratingFactor(8.5).value == 1.0


def test_mrating_above_85_yields_1():
    assert MratingFactor(9.0).value == 1.0
    assert MratingFactor(10.0).value == 1.0


def test_mrating_is_frozen():
    factor = MratingFactor(8.5)
    with pytest.raises(Exception):
        factor.value = 0.3  # type: ignore[misc]


# ---------------------------------------------------------------------------
# score_match_stats — rating modifica el puntaje
# ---------------------------------------------------------------------------

def test_score_match_stats_with_high_rating_scores_more_than_low_rating():
    """Rating >= 8.5 (factor 1.0) should produce more pts than rating < 7.0 (factor 0.3)."""
    svc = SFAScoringService()
    stats = {ActionType.DRIBBLES_WON: 3}

    scores_low = svc.score_match_stats(
        PositionGroup.FW, stats, player_team_pos=5, rival_team_pos=5,
        stage_factor=1.0, rating=6.0,
    )
    scores_high = svc.score_match_stats(
        PositionGroup.FW, stats, player_team_pos=5, rival_team_pos=5,
        stage_factor=1.0, rating=9.0,
    )

    total_low = sum(s.total for s in scores_low)
    total_high = sum(s.total for s in scores_high)
    assert total_high > total_low, (
        f"High rating ({total_high}) should score more than low rating ({total_low})"
    )


def test_score_match_stats_none_rating_matches_half_factor():
    """rating=None and rating=7.5 should produce the same result (both → 0.5)."""
    svc = SFAScoringService()
    stats = {ActionType.DRIBBLES_WON: 3}

    scores_none = svc.score_match_stats(
        PositionGroup.MF, stats, player_team_pos=5, rival_team_pos=5,
        stage_factor=1.0, rating=None,
    )
    scores_avg = svc.score_match_stats(
        PositionGroup.MF, stats, player_team_pos=5, rival_team_pos=5,
        stage_factor=1.0, rating=7.5,
    )

    assert sum(s.total for s in scores_none) == sum(s.total for s in scores_avg)


def test_score_match_stats_default_rating_is_none():
    """Calling without rating arg should behave like rating=None (Mrating=0.5)."""
    svc = SFAScoringService()
    stats = {ActionType.DRIBBLES_WON: 2}

    scores_default = svc.score_match_stats(
        PositionGroup.FW, stats, player_team_pos=5, rival_team_pos=5, stage_factor=1.0
    )
    scores_none = svc.score_match_stats(
        PositionGroup.FW, stats, player_team_pos=5, rival_team_pos=5,
        stage_factor=1.0, rating=None,
    )

    assert sum(s.total for s in scores_default) == sum(s.total for s in scores_none)


# ---------------------------------------------------------------------------
# RecalculateScoresUseCase — delta cambia con rating bajo vs alto
# ---------------------------------------------------------------------------

def _stats_row(rating: float | None, m1: float = 1.0) -> PlayerStatsEventRecalcRow:
    return PlayerStatsEventRecalcRow(
        event_id=1,
        player_id=10,
        player_position="DEL",
        m1=m1,
        m2=1.0,
        current_pts=0.0,
        duels_won=5,
        tackles_won=0,
        interceptions=0,
        blocks=0,
        dribbles_won=3,
        passes_key=0,
        passes_total=0,
        passes_accuracy=0,
        shots_on=0,
        shots_total=0,
        dribbles_past=0,
        duels_total=0,
        fouls_drawn=0,
        fouls_committed=0,
        cards_yellow=0,
        cards_red=0,
        penalty_won=0,
        goals=0,
        assists=0,
        rating=rating,
    )


class FakeEnrichmentRepository:
    """Minimal Fake implementing EnrichmentRepositoryPort for recalc tests."""

    def __init__(
        self,
        stats_rows: list[PlayerStatsEventRecalcRow],
        current_total_pts: float = 0.0,
    ) -> None:
        self._stats_rows = stats_rows
        self._current_total_pts = current_total_pts
        self.updated_pts: dict[int, float] = {}
        self.updated_scores: dict[int, float] = {}

    async def get_players_by_competition(self, competition_id, season):
        return []

    async def get_player_events_without_psxg(self, player_id, competition_id, season):
        return []

    async def update_player_external_ids(self, player_id, fbref_id=None, understat_id=None):
        pass

    async def update_player_stats_from_fbref(self, player_id, season, stats):
        pass

    async def update_event_psxg(self, event_id, psxg):
        pass

    async def update_event_scores(self, event_id, m4, pts):
        pass

    async def update_season_score(self, player_id, competition_id, season, total_pts, matches_played, breakdown):
        self.updated_scores[player_id] = total_pts

    async def get_events_with_psxg_for_recalc(self, competition_id, season):
        return []

    async def get_stats_events_for_recalc(self, competition_id, season):
        return self._stats_rows

    async def update_event_pts(self, event_id, pts, m2=None):
        self.updated_pts[event_id] = pts

    async def get_all_player_season_events(self, player_id, competition_id, season):
        pts = self.updated_pts.get(1, 0.0)
        return [PlayerSeasonEventRow(id=1, player_id=player_id, fixture_id=1, event_type="stats", pts=pts)]

    async def get_player_season_score_row(self, player_id, competition_id, season):
        return SeasonScoreRow(
            player_id=player_id,
            competition_id=competition_id,
            season=season,
            total_pts=self._current_total_pts,
            matches_played=1,
            breakdown={},
        )

    async def get_player_season_real_stats(self, player_id, competition_id, season):
        return (0, 0)


@pytest.mark.anyio
async def test_recalc_high_rating_produces_more_pts_than_low_rating():
    """Events with rating >= 8.5 should recalculate to more pts than rating < 7.0."""
    repo_low = FakeEnrichmentRepository(stats_rows=[_stats_row(rating=6.0)])
    repo_high = FakeEnrichmentRepository(stats_rows=[_stats_row(rating=9.0)])

    uc_low = RecalculateScoresUseCase(repo_low)
    uc_high = RecalculateScoresUseCase(repo_high)

    await uc_low.execute(competition_id=1, season="2024")
    await uc_high.execute(competition_id=1, season="2024")

    pts_low = repo_low.updated_pts.get(1, 0.0)
    pts_high = repo_high.updated_pts.get(1, 0.0)

    assert pts_high > pts_low, (
        f"High rating pts ({pts_high}) should exceed low rating pts ({pts_low})"
    )


@pytest.mark.anyio
async def test_recalc_null_rating_equals_avg_rating():
    """rating=None and rating=7.5 both map to Mrating=0.5, same recalculated pts."""
    repo_none = FakeEnrichmentRepository(stats_rows=[_stats_row(rating=None)])
    repo_avg = FakeEnrichmentRepository(stats_rows=[_stats_row(rating=7.5)])

    await RecalculateScoresUseCase(repo_none).execute(competition_id=1, season="2024")
    await RecalculateScoresUseCase(repo_avg).execute(competition_id=1, season="2024")

    assert repo_none.updated_pts.get(1) == repo_avg.updated_pts.get(1)
