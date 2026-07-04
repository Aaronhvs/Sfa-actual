from __future__ import annotations

import logging

from sfa.domain.ports import SFAScoreRepositoryProtocol
from sfa.domain.ranking_explanation_ports import (
    RankingExplanationGenerationSummaryDTO,
    RankingExplanationRepositoryProtocol,
    RankingExplanationRequestDTO,
    RankingExplanationWriterPort,
)

logger = logging.getLogger(__name__)


class GenerateRankingExplanationsUseCase:
    def __init__(
        self,
        score_repo: SFAScoreRepositoryProtocol,
        explanation_repo: RankingExplanationRepositoryProtocol,
        writer: RankingExplanationWriterPort,
    ) -> None:
        self._score_repo = score_repo
        self._explanation_repo = explanation_repo
        self._writer = writer

    async def execute(self, request: RankingExplanationRequestDTO) -> RankingExplanationGenerationSummaryDTO:
        ranked_players = await self._score_repo.get_ranking(
            season=request.season,
            competition_id=request.competition_id,
            limit=request.limit,
            offset=0,
            rules_version_id=request.rules_version_id,
            use_total=request.use_total,
        )
        evidence_items = await self._explanation_repo.build_evidence(request, ranked_players)
        fresh_hashes = {item.player_id: item.source_hash for item in evidence_items}
        await self._explanation_repo.mark_stale_for_scope(request, fresh_hashes)

        generated = 0
        fallback = 0
        skipped = 0
        failed = 0
        estimated_cost = 0.0

        for evidence in evidence_items:
            current_hash = await self._explanation_repo.get_source_hash(evidence.player_id, request)
            if current_hash == evidence.source_hash and not request.force:
                skipped += 1
                continue
            try:
                result = await self._writer.write(evidence)
            except Exception as exc:  # pragma: no cover - defensive boundary
                logger.exception("[GenerateRankingExplanationsUseCase] writer failed player_id=%s", evidence.player_id)
                from sfa.infrastructure.providers.ranking_explanation_writer import (
                    DeterministicRankingExplanationWriter,
                )

                result = await DeterministicRankingExplanationWriter().write(evidence)
                result = result.__class__(
                    **{**result.__dict__, "error": str(exc)}
                )

            await self._explanation_repo.upsert_explanation(
                evidence=evidence,
                result=result,
                prompt_version="ranking-explanation-v2",
            )
            if result.status == "generated":
                generated += 1
            elif result.status == "fallback":
                fallback += 1
            else:
                failed += 1
            estimated_cost += float(result.cost_estimate_usd or 0)

        return RankingExplanationGenerationSummaryDTO(
            season=request.season,
            competition_id=request.competition_id,
            rules_version_id=request.rules_version_id,
            scope=request.scope,
            generated=generated,
            fallback=fallback,
            skipped=skipped,
            failed=failed,
            estimated_cost_usd=round(estimated_cost, 6),
        )
