from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.get_tournaments import (
    GetTournamentUseCase,
    ListTournamentsUseCase,
)
from sfa.domain.ports import (
    TournamentCompetitionDTO,
    TournamentDetailDTO,
    TournamentFixtureDTO,
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
    )


class FakeTournamentRepository:
    def __init__(self, detail: TournamentDetailDTO | None = None) -> None:
        self.detail = detail

    async def resolve_latest_season(self) -> str | None:
        return "2026"

    async def list_competitions(self, season: str):
        return [_competition()] if season == "2026" else []

    async def get_tournament(self, competition_id: int, season: str):
        if competition_id == 10 and season == "2026":
            return self.detail
        return None


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


@pytest.mark.anyio
async def test_detail_rejects_competition_without_fixtures_in_season():
    with pytest.raises(ValueError, match="not found"):
        await GetTournamentUseCase(FakeTournamentRepository()).execute(99)
