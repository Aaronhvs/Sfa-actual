from __future__ import annotations

import logging

from sfa.application.use_cases.calculate_competition_scores import (
    CalculateCompetitionScoresUseCase,
    CalculateScoresResult,
)
from sfa.domain.ingestion_ports import ScoringRepositoryPort

logger = logging.getLogger(__name__)


class CalculateAllScoresUseCase:
    def __init__(self, repo: ScoringRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, season: str) -> list[CalculateScoresResult]:
        competition_ids = await self._repo.get_competition_ids_with_season(season)
        if not competition_ids:
            logger.info("[CalculateAllScoresUseCase] No competitions found for season=%s", season)
            return []

        results: list[CalculateScoresResult] = []
        for competition_id in competition_ids:
            result = await CalculateCompetitionScoresUseCase(self._repo).execute(
                competition_id, season,
            )
            results.append(result)

        completed = sum(1 for r in results if r.status == "completed")
        logger.info(
            "[CalculateAllScoresUseCase] season=%s competitions=%s completed=%s",
            season, len(results), completed,
        )
        return results
