from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.get_tournament_fixture_detail import (
    GetTournamentFixtureDetailUseCase,
)
from sfa.domain.fixture_detail_ports import (
    FixtureDetailDTO,
    FixtureSFAMomentumBucketDTO,
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
    def __init__(
        self,
        detail: FixtureDetailDTO | None = None,
        missing: bool = False,
    ) -> None:
        self.detail_calls = 0
        self.detail = detail or _detail()
        self.missing = missing

    async def get_fixture_detail(self, fixture_external_id):
        self.detail_calls += 1
        if self.missing:
            return None
        return self.detail if fixture_external_id == 200 else None

    async def get_fixture_events(self, fixture_external_id):
        return [
            FixtureTimelineEventDTO(45, 0, 85, "goal", "Player", None)
        ]

    async def get_fixture_sfa_momentum(
        self,
        fixture_id,
        home_team_id,
        away_team_id,
    ):
        return [FixtureSFAMomentumBucketDTO(40, 45, 120.0, 0.0)]


@pytest.mark.anyio
async def test_returns_current_club_fixture_with_timeline():
    detail_repo = FakeDetailRepository()
    result = await GetTournamentFixtureDetailUseCase(
        FakeTournamentRepository(_local_fixture()),
        detail_repo,
    ).execute(200)

    assert result.fixture.home_team.name == "Paris Saint Germain"
    assert result.events[0].minute == 45
    assert result.sfa_momentum[0].home_points == 120.0
    assert detail_repo.detail_calls == 1


@pytest.mark.anyio
async def test_local_live_snapshot_wins_over_external_final_snapshot():
    local = replace(
        _local_fixture(),
        status="2H",
        home_goals=2,
        away_goals=0,
    )
    external = replace(
        _detail(),
        fixture=replace(
            _detail().fixture,
            status="FT",
            status_label="Match Finished",
            elapsed=90,
            home_goals=3,
            away_goals=0,
            home_winner=True,
            away_winner=False,
        ),
    )

    result = await GetTournamentFixtureDetailUseCase(
        FakeTournamentRepository(local),
        FakeDetailRepository(external),
    ).execute(200)

    assert result.fixture.status == "2H"
    assert result.fixture.status_label == "Segundo tiempo"
    assert result.fixture.home_goals == 2
    assert result.fixture.away_goals == 0
    assert result.fixture.elapsed is None
    assert result.fixture.home_winner is None


@pytest.mark.anyio
async def test_local_final_snapshot_wins_over_external_live_snapshot():
    external = replace(
        _detail(),
        fixture=replace(
            _detail().fixture,
            status="2H",
            status_label="Second Half",
            elapsed=68,
            home_goals=1,
            away_goals=1,
        ),
    )

    result = await GetTournamentFixtureDetailUseCase(
        FakeTournamentRepository(_local_fixture()),
        FakeDetailRepository(external),
    ).execute(200)

    assert result.fixture.status == "FT"
    assert result.fixture.status_label == "Finalizado"
    assert result.fixture.home_goals == 2
    assert result.fixture.away_goals == 1
    assert result.fixture.elapsed is None


@pytest.mark.anyio
async def test_returns_canonical_summary_when_supplement_is_missing():
    result = await GetTournamentFixtureDetailUseCase(
        FakeTournamentRepository(_local_fixture()),
        FakeDetailRepository(missing=True),
    ).execute(200)

    assert result.fixture.status == "FT"
    assert result.fixture.home_goals == 2
    assert result.fixture.away_goals == 1
    assert result.venue.name is None
    assert result.lineups == []


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
