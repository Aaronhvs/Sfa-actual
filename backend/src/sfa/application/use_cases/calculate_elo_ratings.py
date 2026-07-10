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
        source: str = "elo_v1",
        use_seed_baseline: bool = False,
        require_seed_baseline: bool = False,
    ) -> CalculateEloRatingsResult:
        try:
            seeded = await self._repo.get_all_teams_with_elo(season, competition_ids)
            seed_by_team = {row.team_id: row.elo_seed_raw for row in seeded}
            current_elo_by_team = {row.team_id: row.elo_raw for row in seeded}
            fixtures = await self._repo.get_fixtures_for_elo_recalc(season, competition_ids)
            if use_seed_baseline and require_seed_baseline:
                fixture_team_ids = {
                    team_id
                    for fixture in fixtures
                    for team_id in (fixture.home_team_id, fixture.away_team_id)
                }
                missing_seed_team_ids = sorted(
                    team_id
                    for team_id in fixture_team_ids
                    if seed_by_team.get(team_id) is None
                )
                if missing_seed_team_ids:
                    missing = ", ".join(str(team_id) for team_id in missing_seed_team_ids)
                    return CalculateEloRatingsResult(
                        season=season,
                        fixtures_processed=0,
                        teams_updated=0,
                        status="failed",
                        error=f"Missing ELO seed baseline for team_ids: {missing}",
                    )

            elo_by_team = {}
            for team_id, elo_raw in current_elo_by_team.items():
                seed_raw = seed_by_team.get(team_id)
                elo_by_team[team_id] = (
                    seed_raw
                    if use_seed_baseline and seed_raw is not None
                    else elo_raw
                )

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
                    source=source,
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
