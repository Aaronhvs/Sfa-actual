from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring.entities import CompetitionAchievement
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)

logger = logging.getLogger(__name__)

DOMESTIC_LEAGUE_NAMES: list[str] = [
    "Premier League",
    "La Liga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Primeira Liga",
    "Eredivisie",
    "Jupiler Pro League",
    "Süper Lig",
    "Scottish Premiership",
]


@dataclass(frozen=True)
class RefreshLeagueAchievementBonusesResult:
    season: str
    rules_version_id: int
    achievements_refreshed: int
    achievements_skipped: int
    status: str
    error: str | None


class RefreshLeagueAchievementBonusesUseCase:
    def __init__(
        self,
        achievement_repo: CompetitionAchievementRepositoryPort,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
    ) -> None:
        self._achievement_repo = achievement_repo
        self._rules_version_repo = rules_version_repo

    async def execute(
        self,
        season: str,
        rules_version_id: int,
    ) -> RefreshLeagueAchievementBonusesResult:
        rules_version = await self._rules_version_repo.get_version_by_id(rules_version_id)
        if rules_version is None:
            return RefreshLeagueAchievementBonusesResult(
                season=season,
                rules_version_id=rules_version_id,
                achievements_refreshed=0,
                achievements_skipped=0,
                status="failed",
                error=f"Rules version {rules_version_id} not found",
            )

        config = rules_version.config
        domestic_league_bonuses = config.achievement_phase_bonuses.get("domestic_league", {})
        if not domestic_league_bonuses:
            logger.info(
                "[RefreshLeagueAchievementBonusesUseCase] No domestic_league phases in config, skipping"
            )
            return RefreshLeagueAchievementBonusesResult(
                season=season,
                rules_version_id=rules_version_id,
                achievements_refreshed=0,
                achievements_skipped=0,
                status="completed",
                error=None,
            )

        pairs = await self._achievement_repo.get_achievements_for_domestic_leagues(
            season=season,
            league_names=DOMESTIC_LEAGUE_NAMES,
        )

        refreshed = 0
        skipped = 0
        for achievement, competition_name in pairs:
            new_bonus = domestic_league_bonuses.get(achievement.phase)
            if new_bonus is None:
                logger.debug(
                    "[RefreshLeagueAchievementBonusesUseCase] Unknown phase=%s for competition=%s, skipping",
                    achievement.phase,
                    competition_name,
                )
                skipped += 1
                continue

            new_weight = config.competition_bonus_weights.get(competition_name, 1.0)
            updated = CompetitionAchievement(
                id=achievement.id,
                competition_id=achievement.competition_id,
                team_id=achievement.team_id,
                season=achievement.season,
                phase=achievement.phase,
                bonus_points=new_bonus,
                weight=new_weight,
                created_at=achievement.created_at,
            )
            await self._achievement_repo.upsert_achievement(updated)
            logger.debug(
                "[RefreshLeagueAchievementBonusesUseCase] Updated competition=%s phase=%s "
                "bonus_points=%d weight=%.2f",
                competition_name,
                achievement.phase,
                new_bonus,
                new_weight,
            )
            refreshed += 1

        logger.info(
            "[RefreshLeagueAchievementBonusesUseCase] season=%s rules_version_id=%d "
            "refreshed=%d skipped=%d",
            season,
            rules_version_id,
            refreshed,
            skipped,
        )
        return RefreshLeagueAchievementBonusesResult(
            season=season,
            rules_version_id=rules_version_id,
            achievements_refreshed=refreshed,
            achievements_skipped=skipped,
            status="completed",
            error=None,
        )
