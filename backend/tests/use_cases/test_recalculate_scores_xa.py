from __future__ import annotations

import pytest

from sfa.application.use_cases.recalculate_scores import RecalculateScoresUseCase
from sfa.domain.enrichment_ports import (
    EnrichmentRepositoryPort,
    PlayerEnrichDTO,
    PlayerEventRecalcRow,
    PlayerEventRow,
    PlayerSeasonEventRow,
    PlayerStatsEventRecalcRow,
    SeasonScoreRow,
)


# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------

class FakeEnrichmentRepository(EnrichmentRepositoryPort):
    def __init__(
        self,
        stats_events: list[PlayerStatsEventRecalcRow] | None = None,
    ) -> None:
        self._stats_events = stats_events or []
        self.pts_updates: list[tuple[int, float]] = []

    async def get_players_by_competition(self, competition_id: int, season: str) -> list[PlayerEnrichDTO]:
        return []

    async def get_player_events_without_psxg(
        self, player_id: int, competition_id: int, season: str,
    ) -> list[PlayerEventRow]:
        return []

    async def update_player_external_ids(
        self, player_id: int, fbref_id: str | None, understat_id: int | None,
    ) -> None:
        pass

    async def update_player_stats_from_fbref(
        self, player_id: int, season: str, stats: dict,
    ) -> None:
        pass

    async def update_event_psxg(self, event_id: int, psxg: float) -> None:
        pass

    async def update_event_scores(self, event_id: int, m4: float, pts: float) -> None:
        pass

    async def update_season_score(
        self, player_id: int, competition_id: int, season: str,
        total_pts: float, matches_played: int, breakdown: dict,
    ) -> None:
        pass

    async def get_events_with_psxg_for_recalc(
        self, competition_id: int, season: str,
    ) -> list[PlayerEventRecalcRow]:
        return []

    async def get_stats_events_for_recalc(
        self, competition_id: int, season: str,
    ) -> list[PlayerStatsEventRecalcRow]:
        return self._stats_events

    async def update_event_pts(self, event_id: int, pts: float, m2: float | None = None) -> None:
        self.pts_updates.append((event_id, pts))

    async def get_all_player_season_events(
        self, player_id: int, competition_id: int, season: str,
    ) -> list[PlayerSeasonEventRow]:
        return []

    async def get_player_season_score_row(
        self, player_id: int, competition_id: int, season: str,
    ) -> SeasonScoreRow | None:
        return SeasonScoreRow(
            player_id=player_id,
            competition_id=competition_id,
            season=season,
            total_pts=0.0,
            matches_played=1,
            breakdown={},
        )

    async def get_player_season_real_stats(
        self, player_id: int, competition_id: int, season: str,
    ) -> tuple[int, int]:
        return (0, 0)


def _make_stats_event(
    event_id: int = 1,
    player_id: int = 10,
    position: str = "MC",
    passes_key: int = 0,
    assists: int = 0,
    current_pts: float = 0.0,
    m1: float = 1.0,
    rating: float | None = None,
) -> PlayerStatsEventRecalcRow:
    return PlayerStatsEventRecalcRow(
        event_id=event_id,
        player_id=player_id,
        player_position=position,
        m1=m1,
        m2=1.0,
        current_pts=current_pts,
        duels_won=0,
        tackles_won=0,
        interceptions=0,
        blocks=0,
        dribbles_won=0,
        passes_key=passes_key,
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
        assists=assists,
        rating=rating,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRecalculateScoresXa:
    @pytest.mark.anyio
    async def test_xa_no_assist_uses_passes_key_minus_assists(self):
        """XA_NO_ASSIST = max(0, passes_key - assists). Con passes_key=4, assists=1 → count=3 → pts > 0."""
        event = _make_stats_event(passes_key=4, assists=1, current_pts=0.0)
        repo = FakeEnrichmentRepository(stats_events=[event])

        await RecalculateScoresUseCase(repo).execute(competition_id=1, season="2024-2025")

        assert len(repo.pts_updates) == 1
        _, new_pts = repo.pts_updates[0]
        assert new_pts > 0

    @pytest.mark.anyio
    async def test_xa_no_assist_zero_when_no_key_passes(self):
        """Cuando passes_key=0, XA_NO_ASSIST contribuye 0 pts."""
        event = _make_stats_event(passes_key=0, assists=0, current_pts=0.0)
        repo = FakeEnrichmentRepository(stats_events=[event])

        await RecalculateScoresUseCase(repo).execute(competition_id=1, season="2024-2025")

        assert repo.pts_updates == []

    @pytest.mark.anyio
    async def test_xa_no_assist_floor_zero_when_assists_exceed_key_passes(self):
        """passes_key=0, assists=1 → max(0, -1) = 0, sin contribución negativa."""
        event = _make_stats_event(passes_key=0, assists=1, current_pts=0.0)
        repo = FakeEnrichmentRepository(stats_events=[event])

        await RecalculateScoresUseCase(repo).execute(competition_id=1, season="2024-2025")

        assert repo.pts_updates == []
