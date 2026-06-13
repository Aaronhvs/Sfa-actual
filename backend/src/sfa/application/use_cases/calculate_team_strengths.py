from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring.value_objects import TeamStrengthBlend
from sfa.domain.scoring_ports import TeamStrengthRepositoryPort

logger = logging.getLogger(__name__)

_TOTAL_TEAMS_DEFAULT = 20  # fallback when total teams can't be determined


def _position_to_strength(position: float, total_teams: int) -> float:
    """Convert a league table position (1=best) to a 0-100 strength value."""
    if total_teams <= 1:
        return 100.0
    return 100.0 - ((position - 1) / (total_teams - 1)) * 100.0


@dataclass(frozen=True)
class CalculateTeamStrengthsResult:
    season: str
    competition_id: int
    teams_processed: int
    status: str
    error: str | None


class CalculateTeamStrengthsUseCase:
    def __init__(self, repo: TeamStrengthRepositoryPort) -> None:
        self._repo = repo

    async def execute(
        self,
        season: str,
        competition_id: int,
        matchday: int | None = None,
        promoted_champion_strength: float = 35.0,
        promoted_runner_up_strength: float = 30.0,
        promoted_default_strength: float = 30.0,
        league_factor: float = 1.0,
    ) -> CalculateTeamStrengthsResult:
        try:
            current_standings = await self._repo.get_team_standings_for_season(
                competition_id, season
            )
            if not current_standings:
                return CalculateTeamStrengthsResult(
                    season=season, competition_id=competition_id,
                    teams_processed=0, status="completed", error=None,
                )

            total_teams = len(current_standings)

            # Derive previous season string (e.g. "2024" → "2023", "2024-25" → "2023-24")
            prev_season = _decrement_season(season)
            prev_standings = await self._repo.get_team_standings_for_season(
                competition_id, prev_season
            )
            prev_strength_map = {
                row.team_id: _position_to_strength(row.avg_position, len(prev_standings))
                for row in prev_standings
            } if prev_standings else {}

            teams_processed = 0
            for row in current_standings:
                current_strength = _position_to_strength(row.avg_position, total_teams)
                prev_strength = prev_strength_map.get(row.team_id)

                if prev_strength is None:
                    # Newly promoted or no history — use config default
                    prev_strength = promoted_default_strength

                blended = TeamStrengthBlend(
                    prev_season_strength=prev_strength,
                    current_season_strength=current_strength,
                    matchday=matchday,
                )
                final_strength = blended.value * league_factor

                await self._repo.upsert_team_strength(
                    team_id=row.team_id,
                    season=season,
                    competition_id=competition_id,
                    strength=round(final_strength, 2),
                    source="calculated",
                )
                teams_processed += 1

            logger.info(
                "[CalculateTeamStrengthsUseCase] season=%s competition_id=%d teams=%d",
                season, competition_id, teams_processed,
            )
            return CalculateTeamStrengthsResult(
                season=season, competition_id=competition_id,
                teams_processed=teams_processed, status="completed", error=None,
            )

        except Exception as exc:
            logger.exception(
                "[CalculateTeamStrengthsUseCase] Failed season=%s competition_id=%d",
                season, competition_id,
            )
            return CalculateTeamStrengthsResult(
                season=season, competition_id=competition_id,
                teams_processed=0, status="failed", error=str(exc),
            )


def _decrement_season(season: str) -> str:
    """Derive the previous season string.

    "2024"    → "2023"
    "2024-25" → "2023-24"
    "24/25"   → "23/24"
    """
    if "-" in season and len(season) == 7:
        # Format: "2024-25"
        start = int(season[:4])
        return f"{start - 1}-{str(start - 1)[2:]}"
    if "/" in season and len(season) == 5:
        # Format: "24/25"
        start = int(season[:2])
        return f"{start - 1:02d}/{start:02d}"
    try:
        return str(int(season) - 1)
    except ValueError:
        return season
