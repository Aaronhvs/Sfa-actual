from __future__ import annotations

import logging
from dataclasses import replace

from sfa.domain.individual_honors import (
    HonorCandidateStats,
    HonorCompetitionDTO,
    HonorScopeCategory,
    IndividualHonor,
    IndividualHonorRepositoryPort,
    IndividualHonorType,
    InferIndividualHonorsResult,
)
from sfa.domain.ports import SeasonRepositoryProtocol
from sfa.domain.scoring_ports import ScoringRulesVersionRepositoryPort
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind

logger = logging.getLogger(__name__)

DOMESTIC_LEAGUE_NAMES = {
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "Primeira Liga", "Eredivisie", "Jupiler Pro League", "S\u00fcper Lig",
    "Scottish Premiership",
}


class InferIndividualHonorsUseCase:
    def __init__(
        self,
        honor_repo: IndividualHonorRepositoryPort,
        season_repo: SeasonRepositoryProtocol,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
    ) -> None:
        self._honor_repo = honor_repo
        self._season_repo = season_repo
        self._rules_version_repo = rules_version_repo

    async def execute(
        self,
        scope_key: str,
        rules_version_id: int,
    ) -> InferIndividualHonorsResult:
        scope = await self._season_repo.resolve_scope(scope_key)
        if scope is None:
            raise ValueError(f"Scope {scope_key} not found")
        rules_version = await self._rules_version_repo.get_version_by_id(rules_version_id)
        if rules_version is None:
            raise ValueError(f"Rules version {rules_version_id} not found")

        config = rules_version.config
        honors: list[IndividualHonor] = []
        competitions = await self._honor_repo.get_competitions_for_scope(scope)

        overall_category = (
            HonorScopeCategory.WORLD_CUP
            if scope.kind == ScopeKind.TOURNAMENT
            else HonorScopeCategory.AWARD_PERIOD
        )
        overall_candidates = await self._honor_repo.get_candidate_stats(scope)
        honors.extend(self._select_context_honors(
            candidates=overall_candidates,
            scope=scope,
            category=overall_category,
            context_key="overall",
            context_label=scope.label,
            source_season=scope.sources[0].season,
            competition_id=(competitions[0].competition_id if scope.kind == ScopeKind.TOURNAMENT else None),
            points=config.individual_honor_points.get(overall_category.value, {}),
            thresholds=config.individual_honor_thresholds.get(overall_category.value, {}),
            rules_version_id=rules_version_id,
        ))

        if scope.kind == ScopeKind.AWARD_PERIOD:
            for competition in competitions:
                category = self._competition_category(competition)
                if category is None:
                    continue
                candidates = await self._honor_repo.get_candidate_stats(
                    scope, competition.competition_id
                )
                honors.extend(self._select_context_honors(
                    candidates=candidates,
                    scope=scope,
                    category=category,
                    context_key=f"competition:{competition.season}:{competition.competition_id}",
                    context_label=self._competition_label(competition),
                    source_season=competition.season,
                    competition_id=competition.competition_id,
                    points=config.individual_honor_points.get(category.value, {}),
                    thresholds=config.individual_honor_thresholds.get(category.value, {}),
                    rules_version_id=rules_version_id,
                ))

        honors = self._apply_player_cap(honors, config.individual_honor_bonus_cap)
        await self._honor_repo.replace_scope_honors(scope.key, rules_version_id, honors)
        logger.info(
            "[InferIndividualHonorsUseCase] scope=%s honors=%d players=%d",
            scope.key, len(honors), len({honor.player_id for honor in honors}),
        )
        return InferIndividualHonorsResult(
            scope_key=scope.key,
            honors_created=len(honors),
            players_awarded=len({honor.player_id for honor in honors}),
        )

    @staticmethod
    def _competition_category(
        competition: HonorCompetitionDTO,
    ) -> HonorScopeCategory | None:
        if competition.competition_name == "World Cup":
            return HonorScopeCategory.WORLD_CUP
        if competition.competition_name == "Champions League":
            return HonorScopeCategory.CHAMPIONS_LEAGUE
        if competition.competition_name in DOMESTIC_LEAGUE_NAMES:
            return HonorScopeCategory.DOMESTIC_LEAGUE
        return None

    @staticmethod
    def _competition_label(competition: HonorCompetitionDTO) -> str:
        if competition.competition_name == "World Cup":
            return f"Mundial {competition.season}"
        return competition.competition_name

    def _select_context_honors(
        self,
        *,
        candidates: list[HonorCandidateStats],
        scope: AwardPeriodScope,
        category: HonorScopeCategory,
        context_key: str,
        context_label: str,
        source_season: str,
        competition_id: int | None,
        points: dict[str, int],
        thresholds: dict[str, int],
        rules_version_id: int,
    ) -> list[IndividualHonor]:
        if not candidates or not points:
            return []
        min_minutes = int(thresholds.get("min_minutes", 0))
        min_dribbles = int(thresholds.get("min_dribble_attempts", 0))
        selections: list[tuple[IndividualHonorType, HonorCandidateStats]] = []

        scorer = min(candidates, key=lambda item: (-item.goals, -item.assists, item.minutes, item.player_id))
        if scorer.goals > 0:
            selections.append((IndividualHonorType.TOP_SCORER, scorer))

        assister = min(candidates, key=lambda item: (-item.assists, -item.goals, item.minutes, item.player_id))
        if assister.assists > 0:
            selections.append((IndividualHonorType.TOP_ASSISTER, assister))

        dribblers = [
            item for item in candidates
            if item.minutes >= min_minutes
            and item.dribbles_attempts >= min_dribbles
            and item.dribble_rate is not None
        ]
        if dribblers:
            selections.append((
                IndividualHonorType.BEST_DRIBBLER,
                min(
                    dribblers,
                    key=lambda item: (
                        -(item.dribble_rate or 0), -item.dribbles_won,
                        item.minutes, item.player_id,
                    ),
                ),
            ))

        duelists = [
            item for item in candidates
            if item.minutes >= min_minutes and item.duels_total > 0
        ]
        if duelists:
            selections.append((
                IndividualHonorType.DUEL_KING,
                min(
                    duelists,
                    key=lambda item: (
                        -item.duels_won, -(item.duel_rate or 0),
                        item.minutes, item.player_id,
                    ),
                ),
            ))

        return [
            self._build_honor(
                honor_type=honor_type,
                candidate=candidate,
                scope=scope,
                category=category,
                context_key=context_key,
                context_label=context_label,
                source_season=source_season,
                competition_id=competition_id,
                raw_points=int(points.get(honor_type.value, 0)),
                rules_version_id=rules_version_id,
            )
            for honor_type, candidate in selections
            if int(points.get(honor_type.value, 0)) > 0
        ]

    @staticmethod
    def _build_honor(
        *,
        honor_type: IndividualHonorType,
        candidate: HonorCandidateStats,
        scope: AwardPeriodScope,
        category: HonorScopeCategory,
        context_key: str,
        context_label: str,
        source_season: str,
        competition_id: int | None,
        raw_points: int,
        rules_version_id: int,
    ) -> IndividualHonor:
        metric_value: float
        metric_total: int | None = None
        metric_rate: float | None = None
        if honor_type == IndividualHonorType.TOP_SCORER:
            metric_value = float(candidate.goals)
        elif honor_type == IndividualHonorType.TOP_ASSISTER:
            metric_value = float(candidate.assists)
        elif honor_type == IndividualHonorType.BEST_DRIBBLER:
            metric_value = float(candidate.dribbles_won)
            metric_total = candidate.dribbles_attempts
            metric_rate = candidate.dribble_rate
        else:
            metric_value = float(candidate.duels_won)
            metric_total = candidate.duels_total
            metric_rate = candidate.duel_rate

        return IndividualHonor(
            id=None,
            player_id=candidate.player_id,
            scope_key=scope.key,
            scope_label=scope.label,
            context_key=context_key,
            context_label=context_label,
            scope_category=category,
            honor_type=honor_type,
            source_season=source_season,
            competition_id=competition_id,
            rules_version_id=rules_version_id,
            metric_value=metric_value,
            metric_total=metric_total,
            metric_rate=metric_rate,
            raw_bonus_pts=raw_points,
            awarded_bonus_pts=raw_points,
            calculation_details={
                "goals": candidate.goals,
                "assists": candidate.assists,
                "minutes": candidate.minutes,
                "dribbles_won": candidate.dribbles_won,
                "dribbles_attempts": candidate.dribbles_attempts,
                "duels_won": candidate.duels_won,
                "duels_total": candidate.duels_total,
            },
        )

    @staticmethod
    def _apply_player_cap(
        honors: list[IndividualHonor], cap: int
    ) -> list[IndividualHonor]:
        remaining_by_player: dict[int, int] = {}
        awarded_by_identity: dict[tuple[str, str], int] = {}
        ordered = sorted(
            honors,
            key=lambda honor: (
                honor.player_id, -honor.raw_bonus_pts,
                honor.context_key, honor.honor_type.value,
            ),
        )
        for honor in ordered:
            remaining = remaining_by_player.setdefault(honor.player_id, cap)
            awarded = min(honor.raw_bonus_pts, remaining)
            awarded_by_identity[(honor.context_key, honor.honor_type.value)] = awarded
            remaining_by_player[honor.player_id] = remaining - awarded
        return [
            replace(
                honor,
                awarded_bonus_pts=awarded_by_identity[
                    (honor.context_key, honor.honor_type.value)
                ],
            )
            for honor in honors
        ]
