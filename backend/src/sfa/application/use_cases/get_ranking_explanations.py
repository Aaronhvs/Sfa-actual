from datetime import datetime, timezone

from sfa.application.use_cases.generate_ranking_explanations import (
    resolve_explanation_ranking,
)
from sfa.domain.ports import (
    RankedPlayerDTO,
    SeasonRepositoryProtocol,
    SFAScoreRepositoryProtocol,
)
from sfa.domain.ranking_explanation_ports import (
    RankingExplanationRepositoryProtocol,
    RankingExplanationRequestDTO,
    RankingExplanationWriterPort,
    RankingPlayerExplanationDTO,
)


class GetRankingExplanationsUseCase:
    def __init__(
        self,
        repo: RankingExplanationRepositoryProtocol,
        score_repo: SFAScoreRepositoryProtocol | None = None,
        season_repo: SeasonRepositoryProtocol | None = None,
        fallback_writer: RankingExplanationWriterPort | None = None,
    ) -> None:
        self._repo = repo
        self._score_repo = score_repo
        self._season_repo = season_repo
        self._fallback_writer = fallback_writer

    async def execute(self, request: RankingExplanationRequestDTO) -> list[RankingPlayerExplanationDTO]:
        if self._score_repo is None or self._fallback_writer is None:
            return await self._repo.get_cached_for_scope(request)

        resolved_request, ranked_players, source_scope = await resolve_explanation_ranking(
            self._score_repo,
            self._season_repo,
            request,
        )
        cache_matches_context = request.position is None and request.bonus_label is None
        if cache_matches_context:
            cached = await self._repo.get_cached_for_scope(resolved_request)
            if self._cache_matches_ranking(cached, ranked_players, request.limit):
                return cached

        if source_scope is None:
            evidence_items = await self._repo.build_evidence(
                resolved_request,
                ranked_players,
            )
        else:
            evidence_items = await self._repo.build_evidence(
                resolved_request,
                ranked_players,
                source_scope,
            )

        ranked_by_id = {player.player_id: player for player in ranked_players}
        generated_at = datetime.now(timezone.utc)
        results: list[RankingPlayerExplanationDTO] = []
        for evidence in evidence_items:
            written = await self._fallback_writer.write(evidence)
            player = ranked_by_id[evidence.player_id]
            results.append(
                RankingPlayerExplanationDTO(
                    id=0,
                    player_id=evidence.player_id,
                    player_name=player.player_name,
                    team_name=player.team_name,
                    team_logo_url=player.team_logo_url,
                    season=resolved_request.season,
                    competition_id=resolved_request.competition_id,
                    rules_version_id=resolved_request.rules_version_id,
                    scope=resolved_request.scope,
                    rank=evidence.rank,
                    variant=written.variant,
                    status=written.status,
                    short_text=written.short_text,
                    long_text=written.long_text,
                    bullets=written.bullets,
                    evidence=evidence.evidence,
                    model_name=written.model_name,
                    prompt_version="ranking-v8-action-relevance",
                    generated_at=generated_at,
                )
            )
        return results

    @staticmethod
    def _cache_matches_ranking(
        cached: list[RankingPlayerExplanationDTO],
        ranked_players: list[RankedPlayerDTO],
        limit: int,
    ) -> bool:
        expected = ranked_players[:limit]
        if len(cached) < len(expected) or not expected:
            return False
        for explanation, player in zip(cached, expected):
            evidence_player = explanation.evidence.get("player") or {}
            cached_total = round(float(evidence_player.get("total_pts") or 0), 2)
            current_total = round(float(player.total_pts or 0), 2)
            if (
                explanation.player_id != player.player_id
                or explanation.rank != player.rank
                or cached_total != current_total
            ):
                return False
        return True
