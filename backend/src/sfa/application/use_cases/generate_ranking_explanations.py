from __future__ import annotations

import logging
from dataclasses import replace

from sfa.domain.ports import (
    RankedPlayerDTO,
    SeasonRepositoryProtocol,
    SFAScoreRepositoryProtocol,
)
from sfa.domain.ranking_explanation_ports import (
    RankingExplanationGenerationSummaryDTO,
    RankingExplanationRepositoryProtocol,
    RankingExplanationRequestDTO,
    RankingExplanationWriterPort,
)
from sfa.domain.season_scope import AwardPeriodScope, ScopeNotFoundError

logger = logging.getLogger(__name__)


class GenerateRankingExplanationsUseCase:
    def __init__(
        self,
        score_repo: SFAScoreRepositoryProtocol,
        explanation_repo: RankingExplanationRepositoryProtocol,
        writer: RankingExplanationWriterPort,
        season_repo: SeasonRepositoryProtocol | None = None,
    ) -> None:
        self._score_repo = score_repo
        self._explanation_repo = explanation_repo
        self._writer = writer
        self._season_repo = season_repo

    async def execute(self, request: RankingExplanationRequestDTO) -> RankingExplanationGenerationSummaryDTO:
        resolved_request, ranked_players, source_scope = await resolve_explanation_ranking(
            self._score_repo,
            self._season_repo,
            request,
        )
        if source_scope is None:
            evidence_items = await self._explanation_repo.build_evidence(
                resolved_request,
                ranked_players,
            )
        else:
            evidence_items = await self._explanation_repo.build_evidence(
                resolved_request,
                ranked_players,
                source_scope,
            )
        fresh_hashes = {item.player_id: item.source_hash for item in evidence_items}
        await self._explanation_repo.mark_stale_for_scope(resolved_request, fresh_hashes)

        generated = 0
        fallback = 0
        skipped = 0
        failed = 0
        estimated_cost = 0.0

        for evidence in evidence_items:
            current_hash = await self._explanation_repo.get_source_hash(
                evidence.player_id,
                resolved_request,
            )
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
                prompt_version="ranking-v8-action-relevance",
            )
            if result.status == "generated":
                generated += 1
            elif result.status == "fallback":
                fallback += 1
            else:
                failed += 1
            estimated_cost += float(result.cost_estimate_usd or 0)

        return RankingExplanationGenerationSummaryDTO(
            season=resolved_request.season,
            competition_id=resolved_request.competition_id,
            rules_version_id=resolved_request.rules_version_id,
            scope=resolved_request.scope,
            generated=generated,
            fallback=fallback,
            skipped=skipped,
            failed=failed,
            estimated_cost_usd=round(estimated_cost, 6),
        )


async def resolve_explanation_ranking(
    score_repo: SFAScoreRepositoryProtocol,
    season_repo: SeasonRepositoryProtocol | None,
    request: RankingExplanationRequestDTO,
) -> tuple[
    RankingExplanationRequestDTO,
    list[RankedPlayerDTO],
    AwardPeriodScope | None,
]:
    if request.scope_key is None:
        players = await score_repo.get_ranking(
            season=request.season,
            position=request.position,
            competition_id=request.competition_id,
            bonus_label=request.bonus_label,
            limit=request.limit,
            offset=0,
            rules_version_id=request.rules_version_id,
            use_total=request.use_total,
        )
        return request, players, None

    if season_repo is None:
        raise ScopeNotFoundError(request.scope_key)
    source_scope = await season_repo.resolve_scope(request.scope_key)
    if source_scope is None:
        raise ScopeNotFoundError(request.scope_key)
    rules_version_id = await score_repo.resolve_rules_version_id_for_scope(
        source_scope,
        request.rules_version_id,
    )
    resolved_request = replace(request, rules_version_id=rules_version_id)
    players = await score_repo.get_ranking_for_scope(
        scope=source_scope,
        position=request.position,
        competition_id=request.competition_id,
        bonus_label=request.bonus_label,
        limit=request.limit,
        offset=0,
        rules_version_id=rules_version_id,
        use_total=request.use_total,
    )
    return resolved_request, players, source_scope
