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
    "S\u00fcper Lig",
    "Scottish Premiership",
]


@dataclass(frozen=True)
class InferLeagueChampionsResult:
    season: str
    rules_version_id: int
    candidates_found: int
    champions_inferred: int
    candidates_skipped: int
    status: str
    error: str | None


class InferLeagueChampionsUseCase:
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
    ) -> InferLeagueChampionsResult:
        rules_version = await self._rules_version_repo.get_version_by_id(rules_version_id)
        if rules_version is None:
            return InferLeagueChampionsResult(
                season=season,
                rules_version_id=rules_version_id,
                candidates_found=0,
                champions_inferred=0,
                candidates_skipped=0,
                status="failed",
                error=f"Rules version {rules_version_id} not found",
            )

        config = rules_version.config
        champion_points = config.achievement_phase_bonuses.get(
            "domestic_league", {}
        ).get("champion")
        if champion_points is None:
            logger.info(
                "[InferLeagueChampionsUseCase] No domestic_league champion bonus configured, skipping"
            )
            return InferLeagueChampionsResult(
                season=season,
                rules_version_id=rules_version_id,
                candidates_found=0,
                champions_inferred=0,
                candidates_skipped=0,
                status="completed",
                error=None,
            )

        candidates = await self._achievement_repo.get_domestic_league_leaders(
            season=season,
            league_names=DOMESTIC_LEAGUE_NAMES,
        )
        inferred = 0
        skipped = 0
        for candidate in candidates:
            expected_matchday = 2 * (candidate.team_count - 1)
            expected_fixtures = candidate.team_count * (candidate.team_count - 1)
            incomplete = (
                candidate.team_count < 2
                or candidate.matchday < expected_matchday
                or candidate.regular_fixture_count < expected_fixtures
                or candidate.pending_fixture_count > 0
            )
            if incomplete:
                logger.info(
                    "[InferLeagueChampionsUseCase] competition=%s incomplete "
                    "matchday=%d expected=%d fixtures=%d expected_fixtures=%d "
                    "pending=%d teams=%d, skipping",
                    candidate.competition_name,
                    candidate.matchday,
                    expected_matchday,
                    candidate.regular_fixture_count,
                    expected_fixtures,
                    candidate.pending_fixture_count,
                    candidate.team_count,
                )
                skipped += 1
                continue

            achievement = CompetitionAchievement(
                id=None,
                competition_id=candidate.competition_id,
                team_id=candidate.team_id,
                season=candidate.season,
                phase="champion",
                bonus_points=champion_points,
                weight=config.competition_bonus_weights.get(
                    candidate.competition_name, 1.0
                ),
                created_at=None,
            )
            await self._achievement_repo.replace_achievement_for_phase(achievement)
            logger.info(
                "[InferLeagueChampionsUseCase] competition=%s team_id=%d "
                "season=%s champion_points=%d",
                candidate.competition_name,
                candidate.team_id,
                candidate.season,
                champion_points,
            )
            inferred += 1

        logger.info(
            "[InferLeagueChampionsUseCase] season=%s rules_version_id=%d "
            "candidates=%d inferred=%d skipped=%d",
            season,
            rules_version_id,
            len(candidates),
            inferred,
            skipped,
        )
        return InferLeagueChampionsResult(
            season=season,
            rules_version_id=rules_version_id,
            candidates_found=len(candidates),
            champions_inferred=inferred,
            candidates_skipped=skipped,
            status="completed",
            error=None,
        )
