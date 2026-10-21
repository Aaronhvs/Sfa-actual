from sfa.domain.player_positions.ports import SeasonPositionCorrectionRepository
from typing import Protocol
from sfa.domain.player_positions.publication import SeasonPositionCorrectionPlan, PositionPublicationResult


class PublishSeasonPositionCorrectionUseCaseProtocol(Protocol):
    async def execute(self, plan: SeasonPositionCorrectionPlan) -> PositionPublicationResult: ...


class PublishSeasonPositionCorrectionUseCase(PublishSeasonPositionCorrectionUseCaseProtocol):
    def __init__(self, repository: SeasonPositionCorrectionRepository):
        self._repository = repository

    async def execute(self, plan: SeasonPositionCorrectionPlan) -> PositionPublicationResult:
        previous = await self._repository.published(plan.batch_id)
        if previous:
            if previous.status != "published":
                raise ValueError("A reverted batch cannot be silently republished")
            return previous
        if await self._repository.fingerprint(plan.scope_json, plan.rules_version_id) != plan.source_hash:
            raise ValueError("Source/configuration/engine changed; recapture and prepare a new plan")
        return await self._repository.apply(plan)
