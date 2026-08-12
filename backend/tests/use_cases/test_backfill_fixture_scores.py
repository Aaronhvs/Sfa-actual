from __future__ import annotations

import pytest

from sfa.application.use_cases.backfill_fixture_scores import (
    BackfillFixtureScoresUseCase,
)
from sfa.domain.ingestion_ports import (
    FixtureScoreBackfillTargetDTO,
    FixtureScoreRawDTO,
)


def _target(
    fixture_id: int = 1,
    external_id: int = 1001,
    home_team_external_id: int = 10,
    away_team_external_id: int = 20,
) -> FixtureScoreBackfillTargetDTO:
    return FixtureScoreBackfillTargetDTO(
        fixture_id=fixture_id,
        external_id=external_id,
        season="2025",
        status="FT",
        home_team_external_id=home_team_external_id,
        away_team_external_id=away_team_external_id,
    )


def _score(
    external_id: int = 1001,
    status: str = "FT",
    home_team_external_id: int = 10,
    away_team_external_id: int = 20,
    home_goals: int | None = 2,
    away_goals: int | None = 1,
    **kwargs,
) -> FixtureScoreRawDTO:
    return FixtureScoreRawDTO(
        external_id=external_id,
        status=status,
        home_team_external_id=home_team_external_id,
        away_team_external_id=away_team_external_id,
        home_goals=home_goals,
        away_goals=away_goals,
        **kwargs,
    )


class FakeFixtureScoreRepository:
    def __init__(self, targets: list[FixtureScoreBackfillTargetDTO]) -> None:
        self.targets = targets
        self.updates: list[dict] = []

    async def get_missing_fixture_score_targets(
        self,
        seasons: list[str],
    ) -> list[FixtureScoreBackfillTargetDTO]:
        return self.targets

    async def update_fixture_score(
        self,
        fixture_id: int,
        status: str,
        home_goals: int,
        away_goals: int,
        score_source: str,
    ) -> None:
        self.updates.append({
            "fixture_id": fixture_id,
            "status": status,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "score_source": score_source,
        })


class FakeFixtureScoreProvider:
    def __init__(self, rows: dict[int, FixtureScoreRawDTO]) -> None:
        self.rows = rows
        self.batches: list[list[int]] = []

    async def fetch_fixture_scores(
        self,
        external_ids: list[int],
    ) -> list[FixtureScoreRawDTO]:
        self.batches.append(external_ids)
        return [self.rows[item] for item in external_ids if item in self.rows]


@pytest.mark.anyio
async def test_dry_run_validates_every_fixture_without_writing() -> None:
    targets = [_target(fixture_id=index, external_id=1000 + index) for index in range(1, 22)]
    provider = FakeFixtureScoreProvider({
        target.external_id: _score(external_id=target.external_id)
        for target in targets
    })
    repository = FakeFixtureScoreRepository(targets)

    result = await BackfillFixtureScoresUseCase(repository, provider).execute(
        ["2025"],
        dry_run=True,
        batch_size=20,
    )

    assert result.status == "completed"
    assert result.requested == 21
    assert result.validated == 21
    assert result.updated == 0
    assert [len(batch) for batch in provider.batches] == [20, 1]
    assert repository.updates == []


@pytest.mark.anyio
async def test_apply_writes_only_after_full_validation() -> None:
    repository = FakeFixtureScoreRepository([_target()])
    provider = FakeFixtureScoreProvider({
        1001: _score(
            status="PEN",
            home_goals=1,
            away_goals=1,
            fulltime_home_goals=1,
            fulltime_away_goals=1,
            extratime_home_goals=0,
            extratime_away_goals=0,
            shootout_home_goals=5,
            shootout_away_goals=4,
        )
    })

    result = await BackfillFixtureScoresUseCase(repository, provider).execute(
        ["2025"],
        dry_run=False,
    )

    assert result.status == "completed"
    assert result.updated == 1
    assert repository.updates == [{
        "fixture_id": 1,
        "status": "PEN",
        "home_goals": 1,
        "away_goals": 1,
        "score_source": "api_football_backfill",
    }]


@pytest.mark.anyio
async def test_missing_api_fixture_blocks_all_writes() -> None:
    repository = FakeFixtureScoreRepository([
        _target(fixture_id=1, external_id=1001),
        _target(fixture_id=2, external_id=1002),
    ])
    provider = FakeFixtureScoreProvider({1001: _score(external_id=1001)})

    result = await BackfillFixtureScoresUseCase(repository, provider).execute(
        ["2025"],
        dry_run=False,
    )

    assert result.status == "failed"
    assert result.missing_external_ids == (1002,)
    assert repository.updates == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid_row, blocker",
    [
        (_score(home_team_external_id=99), "home team"),
        (_score(status="NS"), "not final"),
        (_score(home_goals=None), "null score"),
        (
            _score(fulltime_home_goals=3, fulltime_away_goals=1),
            "score breakdown",
        ),
        (
            _score(
                status="PEN",
                shootout_home_goals=5,
                shootout_away_goals=5,
            ),
            "invalid shootout",
        ),
    ],
)
async def test_invalid_api_context_blocks_all_writes(
    invalid_row: FixtureScoreRawDTO,
    blocker: str,
) -> None:
    repository = FakeFixtureScoreRepository([_target()])
    provider = FakeFixtureScoreProvider({1001: invalid_row})

    result = await BackfillFixtureScoresUseCase(repository, provider).execute(
        ["2025"],
        dry_run=False,
    )

    assert result.status == "failed"
    assert any(blocker in item for item in result.blockers)
    assert repository.updates == []


@pytest.mark.anyio
async def test_aet_score_is_fulltime_plus_extra_time_goals() -> None:
    repository = FakeFixtureScoreRepository([_target()])
    provider = FakeFixtureScoreProvider({
        1001: _score(
            status="AET",
            home_goals=3,
            away_goals=2,
            fulltime_home_goals=1,
            fulltime_away_goals=1,
            extratime_home_goals=2,
            extratime_away_goals=1,
        )
    })

    result = await BackfillFixtureScoresUseCase(repository, provider).execute(
        ["2025"],
        dry_run=False,
    )

    assert result.status == "completed"
    assert repository.updates[0]["home_goals"] == 3
    assert repository.updates[0]["away_goals"] == 2


@pytest.mark.anyio
async def test_two_legged_penalty_fixture_can_have_non_drawn_match_score() -> None:
    repository = FakeFixtureScoreRepository([_target()])
    provider = FakeFixtureScoreProvider({
        1001: _score(
            status="PEN",
            home_goals=1,
            away_goals=0,
            fulltime_home_goals=1,
            fulltime_away_goals=0,
            shootout_home_goals=3,
            shootout_away_goals=4,
        )
    })

    result = await BackfillFixtureScoresUseCase(repository, provider).execute(
        ["2025"],
        dry_run=False,
    )

    assert result.status == "completed"
    assert repository.updates[0]["home_goals"] == 1
    assert repository.updates[0]["away_goals"] == 0


@pytest.mark.anyio
async def test_no_missing_scores_is_idempotent_and_does_not_call_api() -> None:
    repository = FakeFixtureScoreRepository([])
    provider = FakeFixtureScoreProvider({})

    result = await BackfillFixtureScoresUseCase(repository, provider).execute(
        ["2025", "2026"],
        dry_run=False,
    )

    assert result.status == "completed"
    assert result.requested == 0
    assert provider.batches == []
    assert repository.updates == []
