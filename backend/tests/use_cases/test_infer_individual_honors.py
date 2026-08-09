from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.infer_individual_honors import (
    InferIndividualHonorsUseCase,
)
from sfa.domain.individual_honors import (
    HonorCandidateStats,
    HonorCompetitionDTO,
    IndividualHonor,
    IndividualHonorRepositoryPort,
    IndividualHonorType,
    PlayerIndividualHonorDTO,
)
from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol
from sfa.domain.scoring.entities import ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import ScoringRulesVersionRepositoryPort
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource


class FakeHonorRepository(IndividualHonorRepositoryPort):
    def __init__(
        self,
        candidates: list[HonorCandidateStats],
        competitions: list[HonorCompetitionDTO] | None = None,
    ) -> None:
        self.candidates = candidates
        self.competitions = competitions or []
        self.honors: list[IndividualHonor] = []
        self.replace_calls = 0

    async def get_competitions_for_scope(
        self, scope: AwardPeriodScope
    ) -> list[HonorCompetitionDTO]:
        return self.competitions

    async def get_candidate_stats(
        self,
        scope: AwardPeriodScope,
        competition_id: int | None = None,
    ) -> list[HonorCandidateStats]:
        return self.candidates

    async def replace_scope_honors(
        self,
        scope_key: str,
        rules_version_id: int,
        honors: list[IndividualHonor],
    ) -> None:
        self.replace_calls += 1
        self.honors = list(honors)

    async def get_player_honors(
        self,
        player_id: int,
        rules_version_id: int,
        scope_key: str | None = None,
    ) -> list[PlayerIndividualHonorDTO]:
        return []


class FakeSeasonRepository(SeasonRepositoryProtocol):
    def __init__(self, scope: AwardPeriodScope) -> None:
        self.scope = scope

    async def get_available_seasons(self) -> list[SeasonDTO]:
        return []

    async def resolve_scope(self, scope_key: str | None = None) -> AwardPeriodScope | None:
        return self.scope if scope_key in {None, self.scope.key} else None

    async def get_available_scopes_for_player(self, player_id: int) -> list[SeasonDTO]:
        return []


class FakeRulesRepository(ScoringRulesVersionRepositoryPort):
    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.version = ScoringRulesVersion(
            id=4,
            name="v4",
            version="4",
            description="",
            is_active=True,
            config=config or ScoringConfig.default_v2(),
            created_at=datetime.now(timezone.utc),
        )

    async def get_active_version(self) -> ScoringRulesVersion | None:
        return self.version

    async def get_version_by_id(self, version_id: int) -> ScoringRulesVersion | None:
        return self.version if version_id == self.version.id else None

    async def list_versions(self) -> list[ScoringRulesVersion]:
        return [self.version]

    async def save_version(self, name, version, description, config) -> int:
        return 4

    async def set_active_version(self, version_id: int) -> None:
        return None


def _world_cup_scope() -> AwardPeriodScope:
    return AwardPeriodScope(
        key="world-cup-2026",
        label="Mundial 2026",
        kind=ScopeKind.TOURNAMENT,
        sources=(ScoreSource("2026", (350,)),),
        includes_world_cup=True,
    )


def _award_period_scope() -> AwardPeriodScope:
    return AwardPeriodScope(
        key="season-2025",
        label="2025/2026",
        kind=ScopeKind.AWARD_PERIOD,
        sources=(ScoreSource("2025", (10,)),),
    )


@pytest.mark.anyio
async def test_selects_leaders_and_excludes_small_dribble_sample() -> None:
    candidates = [
        HonorCandidateStats(1, 8, 2, 700, 6, 10, 50, 90),
        HonorCandidateStats(2, 6, 7, 600, 30, 40, 70, 100),
        HonorCandidateStats(3, 2, 1, 190, 9, 9, 10, 20),
    ]
    repo = FakeHonorRepository(candidates, [HonorCompetitionDTO(350, "World Cup", "2026")])
    use_case = InferIndividualHonorsUseCase(
        repo, FakeSeasonRepository(_world_cup_scope()), FakeRulesRepository()
    )

    result = await use_case.execute("world-cup-2026", 4)

    winners = {honor.honor_type: honor.player_id for honor in repo.honors}
    assert winners[IndividualHonorType.TOP_SCORER] == 1
    assert winners[IndividualHonorType.TOP_ASSISTER] == 2
    assert winners[IndividualHonorType.BEST_DRIBBLER] == 2
    assert winners[IndividualHonorType.DUEL_KING] == 2
    assert result.honors_created == 4


@pytest.mark.anyio
async def test_caps_one_players_honors_at_eight_thousand() -> None:
    candidate = HonorCandidateStats(9, 20, 15, 1200, 80, 100, 200, 300)
    repo = FakeHonorRepository([candidate])
    use_case = InferIndividualHonorsUseCase(
        repo, FakeSeasonRepository(_award_period_scope()), FakeRulesRepository()
    )

    await use_case.execute("season-2025", 4)

    assert sum(honor.raw_bonus_pts for honor in repo.honors) == 8200
    assert sum(honor.awarded_bonus_pts for honor in repo.honors) == 8000


@pytest.mark.anyio
async def test_recalculation_replaces_scope_instead_of_duplicating() -> None:
    candidate = HonorCandidateStats(9, 20, 15, 1200, 80, 100, 200, 300)
    repo = FakeHonorRepository([candidate], [HonorCompetitionDTO(350, "World Cup", "2026")])
    use_case = InferIndividualHonorsUseCase(
        repo, FakeSeasonRepository(_world_cup_scope()), FakeRulesRepository()
    )

    await use_case.execute("world-cup-2026", 4)
    first_count = len(repo.honors)
    await use_case.execute("world-cup-2026", 4)

    assert repo.replace_calls == 2
    assert len(repo.honors) == first_count
