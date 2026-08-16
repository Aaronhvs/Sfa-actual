from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.get_tournament_fixture_detail import (
    GetTournamentFixtureDetailUseCase,
)
from sfa.domain.fixture_detail_ports import (
    FixtureDetailDTO,
    FixtureSummaryDTO,
    FixtureTeamDTO,
    FixtureTimelineEventDTO,
    FixtureVenueDTO,
)
from sfa.domain.ports import TournamentFixtureDTO, TournamentTeamDTO


def _local_fixture() -> TournamentFixtureDTO:
    home = TournamentTeamDTO(id=1, external_id=85, name="Paris Saint Germain")
    away = TournamentTeamDTO(id=2, external_id=66, name="Aston Villa")
    return TournamentFixtureDTO(
        id=10,
        external_id=200,
        competition_id=20,
        stage="Final",
        matchday=None,
        played_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        status="FT",
        home_goals=2,
        away_goals=1,
        home_team=home,
        away_team=away,
    )


def _detail() -> FixtureDetailDTO:
    return FixtureDetailDTO(
        fixture=FixtureSummaryDTO(
            external_id=200,
            stage="Final",
            matchday=None,
            played_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
            status="FT",
            status_label="Match Finished",
            elapsed=90,
            home_team=FixtureTeamDTO(85, "Paris Saint Germain"),
            away_team=FixtureTeamDTO(66, "Aston Villa"),
            home_goals=2,
            away_goals=1,
        ),
        venue=FixtureVenueDTO("Salzburg Stadium", "Salzburg"),
        referee=None,
        lineups=[],
        statistics=[],
    )


class FakeTournamentRepository:
    def __init__(self, fixture: TournamentFixtureDTO | None) -> None:
        self.fixture = fixture

    async def resolve_latest_season(self):
        return "2026"

    async def get_fixture_by_external_id(self, fixture_external_id, season):
        if season == "2026" and self.fixture is not None:
            if self.fixture.external_id == fixture_external_id:
                return self.fixture
        return None


class FakeDetailRepository:
    def __init__(self) -> None:
        self.detail_calls = 0

    async def get_fixture_detail(self, fixture_external_id):
        self.detail_calls += 1
        return _detail() if fixture_external_id == 200 else None

    async def get_fixture_events(self, fixture_external_id):
        return [
            FixtureTimelineEventDTO(45, 0, 85, "goal", "Player", None)
        ]


@pytest.mark.anyio
async def test_returns_current_club_fixture_with_timeline():
    detail_repo = FakeDetailRepository()
    result = await GetTournamentFixtureDetailUseCase(
        FakeTournamentRepository(_local_fixture()),
        detail_repo,
    ).execute(200)

    assert result.fixture.home_team.name == "Paris Saint Germain"
    assert result.events[0].minute == 45
    assert detail_repo.detail_calls == 1


@pytest.mark.anyio
async def test_rejects_old_season_before_external_fetch():
    detail_repo = FakeDetailRepository()
    use_case = GetTournamentFixtureDetailUseCase(
        FakeTournamentRepository(_local_fixture()),
        detail_repo,
    )

    with pytest.raises(ValueError, match="current club season"):
        await use_case.execute(200, "2025")

    assert detail_repo.detail_calls == 0


@pytest.mark.anyio
async def test_rejects_fixture_missing_from_local_current_season():
    detail_repo = FakeDetailRepository()
    use_case = GetTournamentFixtureDetailUseCase(
        FakeTournamentRepository(None),
        detail_repo,
    )

    with pytest.raises(ValueError, match="not found"):
        await use_case.execute(200, "2026")

    assert detail_repo.detail_calls == 0
