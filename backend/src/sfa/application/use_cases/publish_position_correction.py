from __future__ import annotations

from sfa.domain.player_positions.ports import PositionCorrectionRepository, PositionCorrectionSimulator
from sfa.domain.player_positions.publication import PositionCorrectionPlan, PositionPublicationResult


class PublishPositionCorrectionUseCase:
    def __init__(self, corrections: PositionCorrectionRepository, simulation: PositionCorrectionSimulator):
        self._corrections, self._simulation = corrections, simulation

    async def execute(self, approved: PositionCorrectionPlan) -> PositionPublicationResult:
        prior = await self._corrections.published(approved.batch_id)
        if prior is not None:
            if prior.status != "published":
                raise ValueError("A reverted correction cannot be silently republished")
            return prior
        current = await self._simulation.execute(approved.request, approved.rules_version_id)
        if current.manifest_hash != approved.manifest_hash:
            raise ValueError("Correction inputs/configuration changed after approval; simulate again")
        return await self._corrections.apply(approved)


class RevertPositionCorrectionUseCase:
    def __init__(self, corrections: PositionCorrectionRepository):
        self._corrections = corrections

    async def execute(self, batch_id: str, actor: str) -> PositionPublicationResult:
        if not actor.strip():
            raise ValueError("Reversion actor is required")
        return await self._corrections.revert(batch_id, actor)
