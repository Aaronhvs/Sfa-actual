"""Tests for EnrichPlayerBirthDatesUseCase (spec 0034)."""
from __future__ import annotations

from datetime import date

import pytest

from sfa.application.use_cases.enrich_player_birth_dates import (
    EnrichPlayerBirthDatesResult,
    EnrichPlayerBirthDatesUseCase,
)
from sfa.domain.enrichment.birth_date_ports import (
    BirthDateEnrichmentRepositoryPort,
    PlayerBirthDateProviderPort,
    PlayerBirthDateRawDTO,
)


class FakeBirthDateProvider(PlayerBirthDateProviderPort):
    def __init__(
        self,
        responses: dict[tuple[int, int], list[PlayerBirthDateRawDTO]],
        player_responses: dict[tuple[int, int], PlayerBirthDateRawDTO | None] | None = None,
    ) -> None:
        self._responses = responses
        self._player_responses = player_responses or {}
        self.calls: list[tuple[int, int]] = []
        self.player_calls: list[tuple[int, int]] = []

    async def fetch_squad_birth_dates(
        self, team_id: int, season: int,
    ) -> list[PlayerBirthDateRawDTO]:
        self.calls.append((team_id, season))
        return self._responses.get((team_id, season), [])

    async def fetch_player_birth_date(
        self,
        player_id: int,
        season: int,
    ) -> PlayerBirthDateRawDTO | None:
        self.player_calls.append((player_id, season))
        return self._player_responses.get((player_id, season))


class FakeBirthDateRepository(BirthDateEnrichmentRepositoryPort):
    def __init__(
        self,
        teams: list[tuple[int, int]],
        players: list[tuple[int, int]] | None = None,
        all_teams: list[tuple[int, int]] | None = None,
        missing_count: int = 5,
        updated_external_ids: set[int] | None = None,
    ) -> None:
        self._teams = teams
        self._players = players or []
        self._all_teams = all_teams if all_teams is not None else teams
        self._missing_count = missing_count
        self._updated_external_ids = updated_external_ids
        self.upserted: list[tuple[int, date | None]] = []
        self.force_flags: list[bool] = []

    async def get_teams_for_birth_date_refresh(self, season: str) -> list[tuple[int, int]]:
        return self._all_teams

    async def get_teams_missing_birth_date(self, season: str) -> list[tuple[int, int]]:
        return self._teams

    async def get_players_missing_birth_date(self, season: str) -> list[tuple[int, int]]:
        return self._players

    async def upsert_player_birth_date(
        self,
        external_id: int,
        birth_date: date | None,
        force_update: bool = False,
    ) -> int:
        self.upserted.append((external_id, birth_date))
        self.force_flags.append(force_update)
        if self._updated_external_ids is not None and external_id not in self._updated_external_ids:
            return 0
        return 1

    async def count_players_missing_birth_date(self) -> int:
        return self._missing_count


@pytest.mark.anyio
async def test_enrich_updates_players_with_missing_birth_date() -> None:
    provider = FakeBirthDateProvider({
        (101, 2026): [
            PlayerBirthDateRawDTO(external_id=1, birth_date=date(2007, 7, 13)),
            PlayerBirthDateRawDTO(external_id=2, birth_date=date(1989, 3, 22)),
        ]
    })
    repo = FakeBirthDateRepository(teams=[(101, 2026)])
    use_case = EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)

    result = await use_case.execute(season="2026")

    assert result.teams_processed == 1
    assert result.players_updated == 2
    assert result.status == "completed"
    assert (1, date(2007, 7, 13)) in repo.upserted
    assert (2, date(1989, 3, 22)) in repo.upserted


@pytest.mark.anyio
async def test_enrich_skips_null_birth_dates_without_force() -> None:
    provider = FakeBirthDateProvider({
        (101, 2026): [
            PlayerBirthDateRawDTO(external_id=1, birth_date=None),
            PlayerBirthDateRawDTO(external_id=2, birth_date=date(1989, 3, 22)),
        ]
    })
    repo = FakeBirthDateRepository(teams=[(101, 2026)])
    use_case = EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)

    result = await use_case.execute(season="2026", force_update=False)

    assert result.players_updated == 1   # only player 2 (has birth_date)
    assert result.players_skipped == 1   # player 1 (birth_date=None, no force)


@pytest.mark.anyio
async def test_enrich_force_update_stores_null_birth_date() -> None:
    provider = FakeBirthDateProvider({
        (101, 2026): [
            PlayerBirthDateRawDTO(external_id=1, birth_date=None),
        ]
    })
    repo = FakeBirthDateRepository(teams=[(101, 2026)])
    use_case = EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)

    result = await use_case.execute(season="2026", force_update=True)

    assert result.players_updated == 1
    assert (1, None) in repo.upserted
    assert repo.force_flags == [True]


@pytest.mark.anyio
async def test_enrich_force_update_uses_all_teams_not_only_missing() -> None:
    provider = FakeBirthDateProvider({
        (101, 2026): [
            PlayerBirthDateRawDTO(external_id=1, birth_date=date(2007, 7, 13)),
        ],
        (102, 2026): [
            PlayerBirthDateRawDTO(external_id=2, birth_date=date(1987, 6, 24)),
        ],
    })
    repo = FakeBirthDateRepository(
        teams=[(101, 2026)],
        all_teams=[(101, 2026), (102, 2026)],
    )
    use_case = EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)

    result = await use_case.execute(season="2026", force_update=True)

    assert result.teams_processed == 2
    assert provider.calls == [(101, 2026), (102, 2026)]
    assert result.players_updated == 2


@pytest.mark.anyio
async def test_enrich_counts_only_actual_updated_rows() -> None:
    provider = FakeBirthDateProvider({
        (101, 2026): [
            PlayerBirthDateRawDTO(external_id=1, birth_date=date(2007, 7, 13)),
            PlayerBirthDateRawDTO(external_id=2, birth_date=date(1987, 6, 24)),
        ]
    })
    repo = FakeBirthDateRepository(
        teams=[(101, 2026)],
        updated_external_ids={1},
    )
    use_case = EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)

    result = await use_case.execute(season="2026")

    assert result.players_updated == 1
    assert result.players_skipped == 1


@pytest.mark.anyio
async def test_enrich_falls_back_to_individual_player_lookup() -> None:
    provider = FakeBirthDateProvider(
        responses={(26, 2026): []},
        player_responses={
            (154, 2026): PlayerBirthDateRawDTO(
                external_id=154,
                birth_date=date(1987, 6, 24),
            ),
        },
    )
    repo = FakeBirthDateRepository(
        teams=[(26, 2026)],
        players=[(154, 2026)],
    )
    use_case = EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)

    result = await use_case.execute(season="2026")

    assert result.teams_processed == 1
    assert result.players_updated == 1
    assert provider.calls == [(26, 2026)]
    assert provider.player_calls == [(154, 2026)]
    assert (154, date(1987, 6, 24)) in repo.upserted


@pytest.mark.anyio
async def test_enrich_handles_provider_error_gracefully() -> None:
    class ErrorProvider(PlayerBirthDateProviderPort):
        async def fetch_squad_birth_dates(self, team_id: int, season: int):
            raise RuntimeError("API quota exceeded")

        async def fetch_player_birth_date(self, player_id: int, season: int):
            raise RuntimeError("API quota exceeded")

    repo = FakeBirthDateRepository(teams=[(101, 2026), (102, 2026)])
    use_case = EnrichPlayerBirthDatesUseCase(provider=ErrorProvider(), repo=repo)

    result = await use_case.execute(season="2026")

    # Both teams fail gracefully — no crash, no players updated
    assert result.teams_processed == 0
    assert result.players_updated == 0
    assert result.status == "completed"


@pytest.mark.anyio
async def test_enrich_no_teams_to_process() -> None:
    provider = FakeBirthDateProvider({})
    repo = FakeBirthDateRepository(teams=[], missing_count=0)
    use_case = EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)

    result = await use_case.execute(season="2026")

    assert result.teams_processed == 0
    assert result.players_updated == 0
    assert result.status == "completed"
