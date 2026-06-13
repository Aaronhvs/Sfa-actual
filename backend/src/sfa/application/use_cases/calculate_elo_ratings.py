from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring_ports import TeamStrengthRepositoryPort

logger = logging.getLogger(__name__)

DEFAULT_K_FACTORS: dict[int, float] = {}
ELO_DEFAULT = 1500.0


@dataclass(frozen=True)
class CalculateEloRatingsResult:
    season: str
    fixtures_processed: int
    teams_updated: int
    status: str
    error: str | None


class CalculateEloRatingsUseCase:
    def __init__(
        self,
        repo: TeamStrengthRepositoryPort,
        calculator,
    ) -> None:
        self._repo = repo
        self._calculator = calculator

    async def execute(
        self,
        season: str,
        competition_ids: list[int],
        k_factors: dict[int, float],
        default_k: float = 30.0,
    ) -> CalculateEloRatingsResult:
        try:
            seeded = await self._repo.get_all_teams_with_elo(season)
            elo_by_team = {row.team_id: row.elo_raw for row in seeded}
            fixtures = await self._repo.get_fixtures_for_elo_recalc(season, competition_ids)

            for fixture in fixtures:
                home_elo = elo_by_team.get(fixture.home_team_id, ELO_DEFAULT)
                away_elo = elo_by_team.get(fixture.away_team_id, ELO_DEFAULT)
                k_factor = k_factors.get(fixture.competition_id, default_k)
                elo_by_team[fixture.home_team_id] = self._calculator.update_elo(
                    current_elo=home_elo,
                    rival_elo=away_elo,
                    home_goals=fixture.home_goals,
                    away_goals=fixture.away_goals,
                    is_home=True,
                    k_factor=k_factor,
                )
                elo_by_team[fixture.away_team_id] = self._calculator.update_elo(
                    current_elo=away_elo,
                    rival_elo=home_elo,
                    home_goals=fixture.home_goals,
                    away_goals=fixture.away_goals,
                    is_home=False,
                    k_factor=k_factor,
                )

            teams_updated = 0
            for team_id, elo_raw in elo_by_team.items():
                team_competition_ids = await self._repo.get_active_competition_ids_for_team(team_id, season)
                if not team_competition_ids:
                    continue
                await self._repo.upsert_team_elo(
                    team_id=team_id,
                    season=season,
                    elo_raw=elo_raw,
                    strength_normalized=self._calculator.normalize(elo_raw),
                    source="elo_v1",
                    competition_ids=team_competition_ids,
                )
                teams_updated += 1

            logger.info(
                "[CalculateEloRatingsUseCase] season=%s fixtures=%d teams_updated=%d",
                season,
                len(fixtures),
                teams_updated,
            )
            return CalculateEloRatingsResult(
                season=season,
                fixtures_processed=len(fixtures),
                teams_updated=teams_updated,
                status="completed",
                error=None,
            )
        except Exception as exc:
            logger.error("[CalculateEloRatingsUseCase] Failed season=%s: %s", season, exc)
            return CalculateEloRatingsResult(
                season=season,
                fixtures_processed=0,
                teams_updated=0,
                status="failed",
                error=str(exc),
            )
