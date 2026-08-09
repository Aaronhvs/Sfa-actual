from __future__ import annotations

import pytest

from sfa.application.use_cases.get_player_individual_honors import (
    GetPlayerIndividualHonorsUseCase,
)
from sfa.domain.individual_honors import PlayerIndividualHonorDTO
from sfa.domain.ports import SeasonDTO
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource


class FakeHonorRepository:
    def __init__(self, honors: list[PlayerIndividualHonorDTO]) -> None:
        self.honors = honors
        self.calls: list[tuple[int, int, str | None]] = []

    async def get_player_honors(
        self,
        player_id: int,
        rules_version_id: int,
        scope_key: str | None = None,
    ) -> list[PlayerIndividualHonorDTO]:
        self.calls.append((player_id, rules_version_id, scope_key))
        return self.honors


class FakeSeasonRepository:
    def __init__(self, scope: AwardPeriodScope | None) -> None:
        self.scope = scope
        self.resolved_keys: list[str | None] = []

    async def resolve_scope(
        self, scope_key: str | None = None
    ) -> AwardPeriodScope | None:
        self.resolved_keys.append(scope_key)
        return self.scope

    async def get_available_seasons(self) -> list[SeasonDTO]:
        return []

    async def get_available_scopes_for_player(
        self, player_id: int
    ) -> list[SeasonDTO]:
        return []


class FakeScoreRepository:
    def __init__(self, resolved_version_id: int = 7) -> None:
        self.resolved_version_id = resolved_version_id
        self.calls: list[tuple[AwardPeriodScope, int | None]] = []

    async def resolve_rules_version_id_for_scope(
        self,
        scope: AwardPeriodScope,
        preferred_rules_version_id: int | None = None,
    ) -> int:
        self.calls.append((scope, preferred_rules_version_id))
        return self.resolved_version_id


def _scope() -> AwardPeriodScope:
    return AwardPeriodScope(
        key="season-2025",
        label="2025/2026",
        kind=ScopeKind.AWARD_PERIOD,
        sources=(ScoreSource("2025", (10,)), ScoreSource("2026", (350,))),
    )


def _honor() -> PlayerIndividualHonorDTO:
    return PlayerIndividualHonorDTO(
        honor_id=3,
        honor_type="top_scorer",
        scope_key="season-2025",
        scope_label="2025/2026",
        context_label="Champions League",
        source_season="2025",
        competition_id=10,
        metric_value=13,
        metric_total=None,
        metric_rate=None,
        bonus_pts=2200,
    )


@pytest.mark.anyio
async def test_reads_scope_with_its_common_rules_version() -> None:
    honor_repo = FakeHonorRepository([_honor()])
    season_repo = FakeSeasonRepository(_scope())
    score_repo = FakeScoreRepository(resolved_version_id=9)
    use_case = GetPlayerIndividualHonorsUseCase(
        honor_repo, season_repo, score_repo, default_rules_version_id=4
    )

    result = await use_case.execute(42, scope_key="season-2025")

    assert result == [_honor()]
    assert season_repo.resolved_keys == ["season-2025"]
    assert score_repo.calls == [(_scope(), 4)]
    assert honor_repo.calls == [(42, 9, "season-2025")]


@pytest.mark.anyio
async def test_all_history_skips_scope_resolution() -> None:
    honor_repo = FakeHonorRepository([_honor()])
    season_repo = FakeSeasonRepository(_scope())
    score_repo = FakeScoreRepository()
    use_case = GetPlayerIndividualHonorsUseCase(
        honor_repo, season_repo, score_repo, default_rules_version_id=4
    )

    result = await use_case.execute(42, all_history=True)

    assert result == [_honor()]
    assert season_repo.resolved_keys == []
    assert score_repo.calls == []
    assert honor_repo.calls == [(42, 4, None)]


@pytest.mark.anyio
async def test_returns_empty_without_a_configured_rules_version() -> None:
    honor_repo = FakeHonorRepository([_honor()])
    use_case = GetPlayerIndividualHonorsUseCase(
        honor_repo,
        FakeSeasonRepository(_scope()),
        FakeScoreRepository(),
        default_rules_version_id=None,
    )

    assert await use_case.execute(42, scope_key="season-2025") == []
    assert honor_repo.calls == []
