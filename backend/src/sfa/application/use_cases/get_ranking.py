from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.ports import RankedPlayerDTO, SFAScoreRepositoryProtocol

ALL_SEASONS_SENTINEL = "all"
DEFAULT_PAGE = 1
DEFAULT_LIMIT = 10
MAX_LIMIT = 50


@dataclass(frozen=True)
class RankingPagination:
    page: int
    limit: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


@dataclass(frozen=True)
class RankingResult:
    season: str
    total: int
    ranking: list[RankedPlayerDTO]
    pagination: RankingPagination


@runtime_checkable
class GetRankingUseCaseProtocol(Protocol):
    async def execute(
        self,
        season: str | None = None,
        position: str | None = None,
        competition_id: int | None = None,
        limit: int = DEFAULT_LIMIT,
        page: int = DEFAULT_PAGE,
        name: str | None = None,
        bonus_label: str | None = None,
        rules_version_id: int | None = None,
        use_total: bool = False,
    ) -> RankingResult: ...


class GetRankingUseCase(GetRankingUseCaseProtocol):
    def __init__(
        self,
        score_repo: SFAScoreRepositoryProtocol,
        default_rules_version_id: int | None = None,
    ) -> None:
        self._score_repo = score_repo
        self._default_rules_version_id = default_rules_version_id

    async def execute(
        self,
        season: str | None = None,
        position: str | None = None,
        competition_id: int | None = None,
        limit: int = DEFAULT_LIMIT,
        page: int = DEFAULT_PAGE,
        name: str | None = None,
        bonus_label: str | None = None,
        rules_version_id: int | None = None,
        use_total: bool = False,
    ) -> RankingResult:
        page = max(page, 1)
        limit = min(max(limit, 1), MAX_LIMIT)
        offset = (page - 1) * limit

        explicit_rules_version = rules_version_id is not None
        if rules_version_id is None:
            rules_version_id = self._default_rules_version_id

        if season is None:
            season = await self._score_repo.latest_season()

        if season is None:
            return RankingResult(
                season="",
                total=0,
                ranking=[],
                pagination=self._pagination(page, limit, 0),
            )

        if season == ALL_SEASONS_SENTINEL:
            ranking = await self._score_repo.get_ranking_all_seasons(
                position, competition_id, limit, offset, name, bonus_label, rules_version_id, use_total,
            )
            total = await self._score_repo.get_ranking_total_all_seasons(
                position, competition_id, name, bonus_label, rules_version_id,
            )
            return RankingResult(
                season=ALL_SEASONS_SENTINEL,
                total=total,
                ranking=ranking,
                pagination=self._pagination(page, limit, total),
            )

        if not explicit_rules_version:
            rules_version_id = await self._score_repo.resolve_rules_version_id_for_season(
                season, rules_version_id,
            )

        ranking = await self._score_repo.get_ranking(
            season, position, competition_id, limit, offset, name, bonus_label, rules_version_id, use_total,
        )
        total = await self._score_repo.get_ranking_total(
            season, position, competition_id, name, bonus_label, rules_version_id,
        )
        return RankingResult(
            season=season,
            total=total,
            ranking=ranking,
            pagination=self._pagination(page, limit, total),
        )

    def _pagination(self, page: int, limit: int, total_items: int) -> RankingPagination:
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 0
        return RankingPagination(
            page=page,
            limit=limit,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1 and total_pages > 0,
        )
