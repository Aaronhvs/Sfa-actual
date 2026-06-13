from __future__ import annotations

import pytest

from sfa.application.use_cases.enrich_with_understat import EnrichWithUnderstatUseCase
from sfa.domain.enrichment_ports import (
    EnrichmentRepositoryPort,
    PlayerEnrichDTO,
    PlayerEventRecalcRow,
    PlayerEventRow,
    PlayerSeasonEventRow,
    PlayerStatsEventRecalcRow,
    SeasonScoreRow,
    UnderstatPlayerDTO,
    UnderstatProviderPort,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeUnderstatProvider(UnderstatProviderPort):
    def __init__(self, players: list[UnderstatPlayerDTO]) -> None:
        self._players = players

    async def fetch_league_players(self, league: str, season: int) -> list[UnderstatPlayerDTO]:
        return self._players


class FakeEnrichmentRepository(EnrichmentRepositoryPort):
    def __init__(self, db_players: list[PlayerEnrichDTO] | None = None) -> None:
        self._db_players = db_players or []
        self.stats_updates: list[tuple[int, str, dict]] = []
        self.external_id_updates: list[tuple[int, int | None]] = []
        self.psxg_updates: list[tuple[int, float]] = []

    async def get_players_by_competition(self, competition_id: int, season: str) -> list[PlayerEnrichDTO]:
        return self._db_players

    async def get_player_events_without_psxg(
        self, player_id: int, competition_id: int, season: str,
    ) -> list[PlayerEventRow]:
        return []

    async def update_player_external_ids(
        self, player_id: int, fbref_id: str | None, understat_id: int | None,
    ) -> None:
        self.external_id_updates.append((player_id, understat_id))

    async def update_player_stats_from_fbref(
        self, player_id: int, season: str, stats: dict,
    ) -> None:
        self.stats_updates.append((player_id, season, stats))

    async def update_event_psxg(self, event_id: int, psxg: float) -> None:
        self.psxg_updates.append((event_id, psxg))

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
        return []

    async def update_event_pts(self, event_id: int, pts: float, m2: float | None = None) -> None:
        pass

    async def get_all_player_season_events(
        self, player_id: int, competition_id: int, season: str,
    ) -> list[PlayerSeasonEventRow]:
        return []

    async def get_player_season_score_row(
        self, player_id: int, competition_id: int, season: str,
    ) -> SeasonScoreRow | None:
        return None

    async def get_player_season_real_stats(
        self, player_id: int, competition_id: int, season: str,
    ) -> tuple[int, int]:
        return (0, 0)


def _make_dto(name: str, xa: float, understat_id: str = "1") -> UnderstatPlayerDTO:
    return UnderstatPlayerDTO(
        player_name=name,
        team_name="Barcelona",
        understat_id=understat_id,
        goals=4,
        assists=5,
        npg=4,
        npxg=3.5,
        xa=xa,
        shots=40,
        key_passes=80,
        xg_per_shot=0.09,
        minutes=2880,
        games=32,
    )


def _make_db_player(player_id: int, name: str) -> PlayerEnrichDTO:
    return PlayerEnrichDTO(id=player_id, name=name, external_id=None, fbref_id=None, understat_id=None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEnrichWithUnderstatUseCaseXa:
    @pytest.mark.anyio
    async def test_xa_written_to_player_stats_when_player_matched(self):
        db_player = _make_db_player(10, "Pedri")
        dto = _make_dto("Pedri", xa=1.8)
        repo = FakeEnrichmentRepository(db_players=[db_player])
        use_case = EnrichWithUnderstatUseCase(FakeUnderstatProvider([dto]), repo)

        result = await use_case.execute("La Liga", 1, "2024-2025", 2024)

        assert len(repo.stats_updates) == 1
        pid, season, stats = repo.stats_updates[0]
        assert pid == 10
        assert season == "2024-2025"
        # xa is normalised to per-fixture: season_xa / games = 1.8 / 32
        assert stats["xa"] == pytest.approx(1.8 / 32, rel=1e-3)
        assert result.stats_enriched == 1

    @pytest.mark.anyio
    async def test_xa_not_written_when_player_not_matched(self):
        db_player = _make_db_player(10, "Pedri")
        dto = _make_dto("Completely Different Name", xa=1.8)
        repo = FakeEnrichmentRepository(db_players=[db_player])
        use_case = EnrichWithUnderstatUseCase(FakeUnderstatProvider([dto]), repo)

        result = await use_case.execute("La Liga", 1, "2024-2025", 2024)

        assert repo.stats_updates == []
        assert result.stats_enriched == 0

    @pytest.mark.anyio
    async def test_xa_not_written_when_dto_xa_is_zero(self):
        db_player = _make_db_player(10, "Pedri")
        dto = _make_dto("Pedri", xa=0.0)
        repo = FakeEnrichmentRepository(db_players=[db_player])
        use_case = EnrichWithUnderstatUseCase(FakeUnderstatProvider([dto]), repo)

        result = await use_case.execute("La Liga", 1, "2024-2025", 2024)

        assert repo.stats_updates == []
        assert result.stats_enriched == 0

    @pytest.mark.anyio
    async def test_stats_enriched_count_reflects_xa_writes(self):
        db_players = [
            _make_db_player(1, "Pedri"),
            _make_db_player(2, "Vitinha"),
            _make_db_player(3, "Busquets"),
        ]
        dtos = [
            _make_dto("Pedri", xa=1.8, understat_id="1"),
            _make_dto("Vitinha", xa=2.1, understat_id="2"),
            _make_dto("Busquets", xa=0.0, understat_id="3"),
        ]
        repo = FakeEnrichmentRepository(db_players=db_players)
        use_case = EnrichWithUnderstatUseCase(FakeUnderstatProvider(dtos), repo)

        result = await use_case.execute("La Liga", 1, "2024-2025", 2024)

        assert result.stats_enriched == 2
        assert len(repo.stats_updates) == 2

    @pytest.mark.anyio
    async def test_champions_league_returns_early_without_xa_writes(self):
        repo = FakeEnrichmentRepository(db_players=[_make_db_player(1, "Pedri")])
        dto = _make_dto("Pedri", xa=1.8)
        use_case = EnrichWithUnderstatUseCase(FakeUnderstatProvider([dto]), repo)

        result = await use_case.execute("Champions League", 1, "2024-2025", 2024)

        assert repo.stats_updates == []
        assert result.stats_enriched == 0
        assert result.status == "completed"
