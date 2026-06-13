from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring.entities import PlayerAchievementBonus
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalculateAchievementBonusesResult:
    season: str
    competition_id: int
    players_updated: int
    bonuses_created: int
    status: str
    error: str | None


def _compute_rank_factor(rank_in_team: int, participation_ratio: float) -> float:
    if participation_ratio < 0.20:
        return 0.50
    if rank_in_team <= 3:
        return 1.20
    if rank_in_team <= 7:
        return 1.10
    if rank_in_team <= 11:
        return 1.00
    return 0.85


def _compute_rating_factor(avg_rating: float | None) -> float:
    if avg_rating is None:
        return 1.00
    if avg_rating >= 8.0:
        return 1.20
    if avg_rating >= 7.5:
        return 1.10
    if avg_rating >= 7.0:
        return 1.00
    if avg_rating >= 6.5:
        return 0.90
    return 0.75


class CalculateAchievementBonusesUseCase:
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
        competition_id: int,
        rules_version_id: int,
    ) -> CalculateAchievementBonusesResult:
        rules_version = await self._rules_version_repo.get_version_by_id(rules_version_id)
        if rules_version is None:
            return CalculateAchievementBonusesResult(
                season=season, competition_id=competition_id,
                players_updated=0, bonuses_created=0, status="failed",
                error=f"ScoringRulesVersion id={rules_version_id} not found",
            )

        config = rules_version.config
        achievements = await self._achievement_repo.get_achievements_for_season(
            competition_id, season
        )
        if not achievements:
            return CalculateAchievementBonusesResult(
                season=season, competition_id=competition_id,
                players_updated=0, bonuses_created=0, status="completed", error=None,
            )

        bonuses_created = 0
        players_updated: set[int] = set()
        player_bonus_totals: dict[int, float] = {}

        for achievement in achievements:
            team_total_minutes = await self._achievement_repo.get_team_total_minutes(
                achievement.team_id, competition_id, season
            )
            if team_total_minutes == 0:
                logger.warning(
                    "[CalculateAchievementBonusesUseCase] team_id=%d has 0 total minutes, skipping",
                    achievement.team_id,
                )
                continue

            player_ids = await self._achievement_repo.get_players_for_team_season(
                achievement.team_id, competition_id, season
            )

            for player_id in player_ids:
                player_minutes = await self._achievement_repo.get_player_minutes_in_competition(
                    player_id, competition_id, season
                )
                final_bonus, details = await self._compute_player_bonus(
                    player_id=player_id,
                    player_minutes=player_minutes,
                    achievement=achievement,
                    team_total_minutes=team_total_minutes,
                    competition_id=competition_id,
                    season=season,
                    rules_version_id=rules_version_id,
                    config=config,
                )

                try:
                    bonus = PlayerAchievementBonus(
                        id=None,
                        player_id=player_id,
                        team_id=achievement.team_id,
                        competition_id=competition_id,
                        season=season,
                        rules_version_id=rules_version_id,
                        achievement_id=achievement.id,  # type: ignore[arg-type]
                        participation_ratio=min(1.0, player_minutes / team_total_minutes),
                        final_bonus=final_bonus,
                        calculation_details=details,
                        created_at=None,
                    )
                except ValueError as exc:
                    logger.warning(
                        "[CalculateAchievementBonusesUseCase] Skipping player_id=%d: %s",
                        player_id, exc,
                    )
                    continue

                await self._achievement_repo.upsert_player_bonus(bonus)
                bonuses_created += 1
                players_updated.add(player_id)
                player_bonus_totals[player_id] = (
                    player_bonus_totals.get(player_id, 0.0) + final_bonus
                )

        for player_id, total_bonus in player_bonus_totals.items():
            await self._achievement_repo.update_season_score_bonus(
                player_id=player_id,
                competition_id=competition_id,
                season=season,
                rules_version_id=rules_version_id,
                bonus_pts=round(total_bonus, 2),
            )

        logger.info(
            "[CalculateAchievementBonusesUseCase] season=%s competition_id=%d "
            "bonuses_created=%d players_updated=%d",
            season, competition_id, bonuses_created, len(players_updated),
        )
        return CalculateAchievementBonusesResult(
            season=season,
            competition_id=competition_id,
            players_updated=len(players_updated),
            bonuses_created=bonuses_created,
            status="completed",
            error=None,
        )

    async def _compute_player_bonus(
        self,
        player_id: int,
        player_minutes: int,
        achievement: object,
        team_total_minutes: int,
        competition_id: int,
        season: str,
        rules_version_id: int,
        config: ScoringConfig,
    ) -> tuple[float, dict]:
        participation_ratio = min(1.0, player_minutes / team_total_minutes)

        if config.enable_performance_based_achievement_bonus:
            rank_in_team = await self._achievement_repo.get_player_rank_in_team(
                player_id, achievement.team_id,  # type: ignore[union-attr]
                competition_id, season, rules_version_id,
            )
            avg_rating = await self._achievement_repo.get_player_avg_rating(
                player_id, competition_id, season
            )
            rank_factor = _compute_rank_factor(rank_in_team, participation_ratio)
            rating_factor = _compute_rating_factor(avg_rating)
            performance_factor = max(0.50, min(1.35, rank_factor * rating_factor))
            final_bonus = round(
                achievement.bonus_points * achievement.weight  # type: ignore[union-attr]
                * participation_ratio * performance_factor, 2
            )
            details = {
                "phase": achievement.phase,  # type: ignore[union-attr]
                "bonus_points": achievement.bonus_points,  # type: ignore[union-attr]
                "competition_weight": achievement.weight,  # type: ignore[union-attr]
                "player_minutes": player_minutes,
                "team_total_minutes": team_total_minutes,
                "participation_ratio": round(participation_ratio, 4),
                "rank_in_team": rank_in_team,
                "rank_factor": rank_factor,
                "avg_rating": avg_rating,
                "rating_factor": rating_factor,
                "performance_factor": round(performance_factor, 4),
                "final_bonus": final_bonus,
            }
        else:
            final_bonus = round(
                achievement.bonus_points * achievement.weight  # type: ignore[union-attr]
                * participation_ratio, 2
            )
            details = {
                "phase": achievement.phase,  # type: ignore[union-attr]
                "bonus_points": achievement.bonus_points,  # type: ignore[union-attr]
                "weight": achievement.weight,  # type: ignore[union-attr]
                "player_minutes": player_minutes,
                "team_total_minutes": team_total_minutes,
                "participation_ratio": round(participation_ratio, 4),
                "final_bonus": final_bonus,
            }

        return final_bonus, details
