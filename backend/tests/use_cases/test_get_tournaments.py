from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from sfa.application.use_cases.get_tournaments import (
    GetTournamentDashboardUseCase,
    GetTournamentUseCase,
    ListTournamentsUseCase,
)
from sfa.domain.ports import (
    TournamentCompetitionDTO,
    TournamentDetailDTO,
    TournamentFixtureDTO,
    TournamentFixtureGroupDTO,
    TournamentTeamDTO,
)


def _competition() -> TournamentCompetitionDTO:
    return TournamentCompetitionDTO(
        id=10,
        name="Champions League",
        country="World",
        season="2026",
        participant_kind="club",
        total_fixtures=2,
        completed_fixtures=1,
        upcoming_fixtures=1,
    )


def _detail() -> TournamentDetailDTO:
    home = TournamentTeamDTO(id=1, external_id=40, name="Liverpool")
    away = TournamentTeamDTO(id=2, external_id=42, name="Arsenal")
    fixture = TournamentFixtureDTO(
        id=100,
        external_id=200,
        competition_id=10,
        stage="League Stage",
        matchday=1,
        played_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        status="NS",
        home_goals=None,
        away_goals=None,
        home_team=home,
        away_team=away,
    )
    return TournamentDetailDTO(
        competition=_competition(),
        standings_matchday=None,
        fixtures=(fixture,),
        standings=(),
        champion=home,
    )


class FakeTournamentRepository:
    def __init__(
        self,
        detail: TournamentDetailDTO | None = None,
        dates: list[date] | None = None,
    ) -> None:
        self.detail = detail
        self.dates = dates or []

    async def resolve_latest_season(self) -> str | None:
        return "2026"

    async def list_competitions(self, season: str):
        return [_competition()] if season == "2026" else []

    async def get_tournament(self, competition_id: int, season: str):
        if competition_id == 10 and season == "2026":
            return self.detail
        return None

    async def list_fixture_dates(self, season: str):
        return self.dates if season == "2026" else []

    async def get_fixture_groups(self, season: str, fixture_date: date):
        if season != "2026" or fixture_date not in self.dates:
            return []
        return [
            TournamentFixtureGroupDTO(
                competition=_competition(),
                fixtures=_detail().fixtures,
            )
        ]


@pytest.mark.anyio
async def test_catalog_resolves_latest_club_season():
    result = await ListTournamentsUseCase(FakeTournamentRepository()).execute()

    assert result.season == "2026"
    assert result.competitions[0].name == "Champions League"


@pytest.mark.anyio
async def test_detail_returns_fixtures_and_allows_empty_standings():
    result = await GetTournamentUseCase(
        FakeTournamentRepository(_detail())
    ).execute(10)

    assert result.fixtures[0].status == "NS"
    assert result.standings == ()
    assert result.champion is not None
    assert result.champion.name == "Liverpool"


@pytest.mark.anyio
async def test_detail_rejects_competition_without_fixtures_in_season():
    with pytest.raises(ValueError, match="not found"):
        await GetTournamentUseCase(FakeTournamentRepository()).execute(99)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("today", "dates", "expected"),
    [
        (date(2026, 8, 15), [date(2026, 8, 15), date(2026, 8, 16)], date(2026, 8, 15)),
        (date(2026, 8, 15), [date(2026, 8, 16), date(2026, 8, 17)], date(2026, 8, 16)),
        (date(2026, 8, 18), [date(2026, 8, 16), date(2026, 8, 17)], date(2026, 8, 17)),
    ],
)
async def test_dashboard_resolves_nearest_fixture_date(today, dates, expected):
    result = await GetTournamentDashboardUseCase(
        FakeTournamentRepository(dates=dates),
        today_provider=lambda: today,
    ).execute()

    assert result.selected_date == expected
    assert len(result.groups) == 1


@pytest.mark.anyio
async def test_dashboard_preserves_explicit_empty_date_and_adjacent_dates():
    result = await GetTournamentDashboardUseCase(
        FakeTournamentRepository(
            dates=[date(2026, 8, 14), date(2026, 8, 16)],
        )
    ).execute(fixture_date=date(2026, 8, 15))

    assert result.selected_date == date(2026, 8, 15)
    assert result.previous_date == date(2026, 8, 14)
    assert result.next_date == date(2026, 8, 16)
    assert result.groups == ()


@pytest.mark.anyio
async def test_dashboard_allows_season_without_fixtures():
    result = await GetTournamentDashboardUseCase(
        FakeTournamentRepository(),
    ).execute()

    assert result.selected_date is None
    assert result.previous_date is None
    assert result.next_date is None
    assert result.groups == ()
