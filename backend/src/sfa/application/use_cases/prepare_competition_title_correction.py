from __future__ import annotations

from sfa.domain.title_correction import (
    TitleCorrectionPlan,
    TitleCorrectionRepositoryPort,
    fingerprint,
    validate_evidence,
)


class PrepareCompetitionTitleCorrectionUseCase:
    def __init__(self, repository: TitleCorrectionRepositoryPort) -> None:
        self._repository = repository

    async def execute(self, evidence: str) -> TitleCorrectionPlan:
        data = validate_evidence(evidence)
        await self._repository.lock()
        before = await self._repository.snapshot(evidence)
        return TitleCorrectionPlan(evidence, fingerprint(data), before)
