from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.application.use_cases.calculate_achievement_bonuses import (
    CalculateAchievementBonusesUseCase,
)
from sfa.application.use_cases.calculate_scores_for_rules_version import (
    CalculateScoresForRulesVersionUseCase,
)
from sfa.application.use_cases.infer_competition_achievements import (
    InferAllCompetitionAchievementsUseCase,
)
from sfa.application.use_cases.refresh_league_achievement_bonuses import (
    RefreshLeagueAchievementBonusesUseCase,
)
from sfa.domain.infer_achievements_ports import InferAchievementsRepositoryPort
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    PlayerEventScoreRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunFullRecalculationResult:
    rules_version_id: int
    season: str
    events_calculated: int
    players_updated: int
    competitions_with_bonuses: int
    achievement_bonuses_created: int
    status: str
    error: str | None


class RunFullRecalculationUseCase:
    def __init__(
        self,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
        event_score_repo: PlayerEventScoreRepositoryPort,
        achievement_repo: CompetitionAchievementRepositoryPort,
        infer_repo: InferAchievementsRepositoryPort | None = None,
    ) -> None:
        self._rules_version_repo = rules_version_repo
        self._event_score_repo = event_score_repo
        self._achievement_repo = achievement_repo
        self._infer_repo = infer_repo

    async def execute(
        self,
        rules_version_id: int,
        season: str,
        force_recalculate: bool = True,
        infer_achievements: bool = True,
    ) -> RunFullRecalculationResult:
        scoring_uc = CalculateScoresForRulesVersionUseCase(
            rules_version_repo=self._rules_version_repo,
            event_score_repo=self._event_score_repo,
        )
        scoring_result = await scoring_uc.execute(
            rules_version_id=rules_version_id,
            season=season,
            force_recalculate=force_recalculate,
        )
        if scoring_result.status == "failed":
            return RunFullRecalculationResult(
                rules_version_id=rules_version_id,
                season=season,
                events_calculated=0,
                players_updated=0,
                competitions_with_bonuses=0,
                achievement_bonuses_created=0,
                status="failed",
                error=scoring_result.error,
            )

        if infer_achievements and self._infer_repo is not None:
            infer_uc = InferAllCompetitionAchievementsUseCase(
                infer_repo=self._infer_repo,
                achievement_repo=self._achievement_repo,
                rules_version_repo=self._rules_version_repo,
            )
            infer_result = await infer_uc.execute(
                season=season,
                rules_version_id=rules_version_id,
            )
            logger.info(
                "[RunFullRecalculationUseCase] infer_achievements done: "
                "processed=%d skipped=%d upserted=%d",
                infer_result.competitions_processed,
                infer_result.competitions_skipped,
                infer_result.total_achievements_upserted,
            )

        refresh_uc = RefreshLeagueAchievementBonusesUseCase(
            achievement_repo=self._achievement_repo,
            rules_version_repo=self._rules_version_repo,
        )
        refresh_result = await refresh_uc.execute(
            season=season,
            rules_version_id=rules_version_id,
        )
        logger.info(
            "[RunFullRecalculationUseCase] refresh_league_bonuses: "
            "refreshed=%d skipped=%d status=%s",
            refresh_result.achievements_refreshed,
            refresh_result.achievements_skipped,
            refresh_result.status,
        )

        competition_ids = await self._achievement_repo.get_competition_ids_for_season(season)
        bonus_uc = CalculateAchievementBonusesUseCase(
            achievement_repo=self._achievement_repo,
            rules_version_repo=self._rules_version_repo,
        )

        total_bonuses_created = 0
        for competition_id in competition_ids:
            bonus_result = await bonus_uc.execute(
                season=season,
                competition_id=competition_id,
                rules_version_id=rules_version_id,
            )
            total_bonuses_created += bonus_result.bonuses_created
            logger.info(
                "[RunFullRecalculationUseCase] competition_id=%d bonuses_created=%d status=%s",
                competition_id,
                bonus_result.bonuses_created,
                bonus_result.status,
            )

        logger.info(
            "[RunFullRecalculationUseCase] COMPLETE season=%s rules_version_id=%d "
            "events=%d players=%d competitions_with_bonuses=%d total_bonuses=%d",
            season,
            rules_version_id,
            scoring_result.events_calculated,
            scoring_result.players_updated,
            len(competition_ids),
            total_bonuses_created,
        )
        return RunFullRecalculationResult(
            rules_version_id=rules_version_id,
            season=season,
            events_calculated=scoring_result.events_calculated,
            players_updated=scoring_result.players_updated,
            competitions_with_bonuses=len(competition_ids),
            achievement_bonuses_created=total_bonuses_created,
            status="completed",
            error=None,
        )
