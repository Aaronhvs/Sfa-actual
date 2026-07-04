from sfa.domain.ranking_explanation_ports import (
    RankingExplanationRepositoryProtocol,
    RankingExplanationRequestDTO,
    RankingPlayerExplanationDTO,
)


class GetPlayerRankingExplanationUseCase:
    def __init__(self, repo: RankingExplanationRepositoryProtocol) -> None:
        self._repo = repo

    async def execute(
        self,
        player_id: int,
        request: RankingExplanationRequestDTO,
    ) -> RankingPlayerExplanationDTO | None:
        return await self._repo.get_cached_for_player(player_id, request)
