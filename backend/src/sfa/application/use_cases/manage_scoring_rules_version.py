from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring.entities import ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import ScoringRulesVersionRepositoryPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreateScoringRulesVersionResult:
    version_id: int
    name: str
    version: str
    status: str
    error: str | None


@dataclass(frozen=True)
class ActivateScoringRulesVersionResult:
    version_id: int
    status: str
    error: str | None


@dataclass(frozen=True)
class ListScoringRulesVersionsResult:
    versions: list[ScoringRulesVersion]


class CreateScoringRulesVersionUseCase:
    def __init__(self, repo: ScoringRulesVersionRepositoryPort) -> None:
        self._repo = repo

    async def execute(
        self,
        name: str,
        version: str,
        description: str,
        config_dict: dict,
    ) -> CreateScoringRulesVersionResult:
        try:
            config = ScoringConfig.from_dict(config_dict)
        except ValueError as exc:
            return CreateScoringRulesVersionResult(
                version_id=0, name=name, version=version,
                status="failed", error=str(exc),
            )

        version_id = await self._repo.save_version(
            name=name, version=version, description=description, config=config,
        )
        logger.info(
            "[CreateScoringRulesVersionUseCase] Created version id=%d name=%s version=%s",
            version_id, name, version,
        )
        return CreateScoringRulesVersionResult(
            version_id=version_id, name=name, version=version,
            status="created", error=None,
        )


class ActivateScoringRulesVersionUseCase:
    def __init__(self, repo: ScoringRulesVersionRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, version_id: int) -> ActivateScoringRulesVersionResult:
        try:
            await self._repo.set_active_version(version_id)
        except ValueError as exc:
            return ActivateScoringRulesVersionResult(
                version_id=version_id, status="failed", error=str(exc),
            )
        logger.info(
            "[ActivateScoringRulesVersionUseCase] Activated version id=%d", version_id,
        )
        return ActivateScoringRulesVersionResult(
            version_id=version_id, status="activated", error=None,
        )


class ListScoringRulesVersionsUseCase:
    def __init__(self, repo: ScoringRulesVersionRepositoryPort) -> None:
        self._repo = repo

    async def execute(self) -> ListScoringRulesVersionsResult:
        versions = await self._repo.list_versions()
        return ListScoringRulesVersionsResult(versions=versions)
