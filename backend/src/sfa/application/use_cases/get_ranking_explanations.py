from sfa.domain.ranking_explanation_ports import (
    RankingExplanationRepositoryProtocol,
    RankingExplanationRequestDTO,
    RankingPlayerExplanationDTO,
)


class GetRankingExplanationsUseCase:
    def __init__(self, repo: RankingExplanationRepositoryProtocol) -> None:
        self._repo = repo

    async def execute(self, request: RankingExplanationRequestDTO) -> list[RankingPlayerExplanationDTO]:
        return await self._repo.get_cached_for_scope(request)
