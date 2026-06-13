from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring.entities import CompetitionAchievement
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegisterAchievementResult:
    achievement_id: int
    status: str
    error: str | None


class RegisterCompetitionAchievementUseCase:
    def __init__(
        self,
        achievement_repo: CompetitionAchievementRepositoryPort,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
    ) -> None:
        self._achievement_repo = achievement_repo
        self._rules_version_repo = rules_version_repo

    async def execute(
        self,
        competition_id: int,
        team_id: int,
        season: str,
        phase: str,
        rules_version_id: int,
        competition_name: str = "",
    ) -> RegisterAchievementResult:
        rules_version = await self._rules_version_repo.get_version_by_id(rules_version_id)
        if rules_version is None:
            return RegisterAchievementResult(
                achievement_id=0, status="failed",
                error=f"ScoringRulesVersion id={rules_version_id} not found",
            )

        config = rules_version.config

        # Resolve bonus_points and weight from config
        bonus_points: int | None = None
        weight: float | None = None

        for category, phases in config.achievement_phase_bonuses.items():
            if phase in phases:
                bonus_points = phases[phase]
                break

        if bonus_points is None:
            valid_phases = [
                p for phases in config.achievement_phase_bonuses.values()
                for p in phases
            ]
            return RegisterAchievementResult(
                achievement_id=0, status="failed",
                error=f"Phase '{phase}' not found in config. Valid: {sorted(set(valid_phases))}",
            )

        weight = config.competition_bonus_weights.get(competition_name, 1.0)

        try:
            achievement = CompetitionAchievement(
                id=None,
                competition_id=competition_id,
                team_id=team_id,
                season=season,
                phase=phase,
                bonus_points=bonus_points,
                weight=weight,
                created_at=None,
            )
        except ValueError as exc:
            return RegisterAchievementResult(
                achievement_id=0, status="failed", error=str(exc),
            )

        achievement_id = await self._achievement_repo.upsert_achievement(achievement)

        logger.info(
            "[RegisterCompetitionAchievementUseCase] achievement_id=%d "
            "competition_id=%d team_id=%d season=%s phase=%s bonus=%d weight=%.3f",
            achievement_id, competition_id, team_id, season, phase, bonus_points, weight,
        )
        return RegisterAchievementResult(
            achievement_id=achievement_id, status="registered", error=None,
        )
