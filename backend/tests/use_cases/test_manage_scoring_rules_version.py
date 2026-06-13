from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.manage_scoring_rules_version import (
    ActivateScoringRulesVersionUseCase,
    CreateScoringRulesVersionUseCase,
    ListScoringRulesVersionsUseCase,
)
from sfa.domain.scoring.entities import ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import ScoringRulesVersionRepositoryPort


class FakeScoringRulesVersionRepository(ScoringRulesVersionRepositoryPort):
    def __init__(self):
        self._versions: dict[int, ScoringRulesVersion] = {}
        self._next_id = 1

    async def get_active_version(self) -> ScoringRulesVersion | None:
        return next((v for v in self._versions.values() if v.is_active), None)

    async def get_version_by_id(self, version_id: int) -> ScoringRulesVersion | None:
        return self._versions.get(version_id)

    async def list_versions(self) -> list[ScoringRulesVersion]:
        return sorted(self._versions.values(), key=lambda v: v.created_at, reverse=True)

    async def save_version(
        self,
        name: str,
        version: str,
        description: str,
        config: ScoringConfig,
    ) -> int:
        vid = self._next_id
        self._next_id += 1
        self._versions[vid] = ScoringRulesVersion(
            id=vid,
            name=name,
            version=version,
            description=description,
            is_active=False,
            config=config,
            created_at=datetime.now(timezone.utc),
        )
        return vid

    async def set_active_version(self, version_id: int) -> None:
        if version_id not in self._versions:
            raise ValueError(f"ScoringRulesVersion id={version_id} not found")
        updated: dict[int, ScoringRulesVersion] = {}
        for vid, v in self._versions.items():
            updated[vid] = ScoringRulesVersion(
                id=v.id, name=v.name, version=v.version, description=v.description,
                is_active=(vid == version_id), config=v.config, created_at=v.created_at,
            )
        self._versions = updated


def _default_config_dict() -> dict:
    return ScoringConfig.default().to_dict()


class TestCreateScoringRulesVersionUseCase:
    @pytest.mark.anyio
    async def test_create_valid_version_returns_id(self):
        repo = FakeScoringRulesVersionRepository()
        use_case = CreateScoringRulesVersionUseCase(repo)

        result = await use_case.execute(
            name="v1.0-test",
            version="1.0.0",
            description="Test version",
            config_dict=_default_config_dict(),
        )

        assert result.status == "created"
        assert result.version_id > 0
        assert result.error is None

    @pytest.mark.anyio
    async def test_create_version_with_invalid_config_returns_failed(self):
        repo = FakeScoringRulesVersionRepository()
        use_case = CreateScoringRulesVersionUseCase(repo)

        result = await use_case.execute(
            name="v-bad",
            version="0.0.1",
            description="",
            config_dict={"base_points": {}},
        )

        assert result.status == "failed"
        assert result.error is not None
        assert result.version_id == 0


class TestActivateScoringRulesVersionUseCase:
    @pytest.mark.anyio
    async def test_activate_version_sets_is_active_true(self):
        repo = FakeScoringRulesVersionRepository()
        await repo.save_version("v1", "1.0.0", "", ScoringConfig.default())
        use_case = ActivateScoringRulesVersionUseCase(repo)

        result = await use_case.execute(version_id=1)

        assert result.status == "activated"
        assert result.error is None
        active = await repo.get_active_version()
        assert active is not None
        assert active.id == 1
        assert active.is_active is True

    @pytest.mark.anyio
    async def test_activate_version_deactivates_others(self):
        repo = FakeScoringRulesVersionRepository()
        await repo.save_version("v1", "1.0.0", "", ScoringConfig.default())
        await repo.save_version("v2", "2.0.0", "", ScoringConfig.default())
        await repo.set_active_version(1)

        use_case = ActivateScoringRulesVersionUseCase(repo)
        await use_case.execute(version_id=2)

        v1 = await repo.get_version_by_id(1)
        v2 = await repo.get_version_by_id(2)
        assert v1.is_active is False
        assert v2.is_active is True

    @pytest.mark.anyio
    async def test_activate_nonexistent_version_returns_failed(self):
        repo = FakeScoringRulesVersionRepository()
        use_case = ActivateScoringRulesVersionUseCase(repo)

        result = await use_case.execute(version_id=999)

        assert result.status == "failed"
        assert result.error is not None


class TestListScoringRulesVersionsUseCase:
    @pytest.mark.anyio
    async def test_list_returns_all_versions(self):
        repo = FakeScoringRulesVersionRepository()
        await repo.save_version("v1", "1.0.0", "", ScoringConfig.default())
        await repo.save_version("v2", "2.0.0", "", ScoringConfig.default())
        use_case = ListScoringRulesVersionsUseCase(repo)

        result = await use_case.execute()

        assert len(result.versions) == 2

    @pytest.mark.anyio
    async def test_list_empty_when_no_versions(self):
        repo = FakeScoringRulesVersionRepository()
        use_case = ListScoringRulesVersionsUseCase(repo)

        result = await use_case.execute()

        assert result.versions == []
