from __future__ import annotations

from sfa.domain.event_integrity import IntegrityPlan, prepare_plan
from sfa.domain.event_integrity_ports import SeasonEventIntegrityRepositoryPort


class PrepareSeasonEventIntegrityUseCase:
    def __init__(self, repository: SeasonEventIntegrityRepositoryPort) -> None:
        self._repository = repository

    async def execute(
        self, fixture_id: int, source: dict, stats_source: dict | None = None, fixture_source: dict | None = None
    ) -> IntegrityPlan:
        return prepare_plan(await self._repository.snapshot(fixture_id), source, stats_source, fixture_source)
