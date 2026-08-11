from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring_ports import (
    FixtureTeamStrengthDTO,
    TeamStrengthRepositoryPort,
)

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
        initialize_missing_seed_baseline: bool = False,
        participant_kind: str | None = None,
    ) -> CalculateEloRatingsResult:
        try:
            resolved_kind = participant_kind or (
                "national_team" if source.startswith("national_") else "club"
            )
            current_rows = (
                []
                if use_seed_baseline
                else await self._repo.get_all_teams_with_elo(season, competition_ids)
            )
            current_elo_by_team = {row.team_id: row.elo_raw for row in current_rows}
            seed_rows = (
                await self._repo.get_team_elo_seeds(season, resolved_kind)
                if use_seed_baseline
                else []
            )
            seed_by_team = {row.team_id: row.elo_raw for row in seed_rows}
            seed_source_by_team = {row.team_id: row.source for row in seed_rows}
            fixtures = await self._repo.get_fixtures_for_elo_recalc(season, competition_ids)
            fixture_team_ids = {
                team_id
                for fixture in fixtures
                for team_id in (fixture.home_team_id, fixture.away_team_id)
            }
            if use_seed_baseline and require_seed_baseline:
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
            if use_seed_baseline and initialize_missing_seed_baseline:
                for team_id in fixture_team_ids:
                    if seed_by_team.get(team_id) is None:
                        seed_by_team[team_id] = ELO_DEFAULT
                        seed_source_by_team[team_id] = "synthetic_default"
                    current_elo_by_team.setdefault(team_id, seed_by_team[team_id])

            elo_by_team = (
                dict(seed_by_team)
                if use_seed_baseline
                else dict(current_elo_by_team)
            )

            snapshots: list[FixtureTeamStrengthDTO] = []
            for fixture in fixtures:
                home_elo = elo_by_team.get(fixture.home_team_id, ELO_DEFAULT)
                away_elo = elo_by_team.get(fixture.away_team_id, ELO_DEFAULT)
                k_factor = k_factors.get(fixture.competition_id, default_k)
                home_post_elo = self._calculator.update_elo(
                    current_elo=home_elo,
                    rival_elo=away_elo,
                    home_goals=fixture.home_goals,
                    away_goals=fixture.away_goals,
                    is_home=True,
                    k_factor=k_factor,
                )
                away_post_elo = self._calculator.update_elo(
                    current_elo=away_elo,
                    rival_elo=home_elo,
                    home_goals=fixture.home_goals,
                    away_goals=fixture.away_goals,
                    is_home=False,
                    k_factor=k_factor,
                )
                snapshots.extend((
                    FixtureTeamStrengthDTO(
                        fixture_id=fixture.fixture_id,
                        team_id=fixture.home_team_id,
                        season=fixture.season,
                        competition_id=fixture.competition_id,
                        participant_kind=resolved_kind,
                        pre_match_elo_raw=home_elo,
                        post_match_elo_raw=home_post_elo,
                        pre_match_strength=self._calculator.normalize(home_elo),
                        post_match_strength=self._calculator.normalize(home_post_elo),
                        model_version=source,
                        seed_source=seed_source_by_team.get(
                            fixture.home_team_id, "legacy_projection"
                        ),
                    ),
                    FixtureTeamStrengthDTO(
                        fixture_id=fixture.fixture_id,
                        team_id=fixture.away_team_id,
                        season=fixture.season,
                        competition_id=fixture.competition_id,
                        participant_kind=resolved_kind,
                        pre_match_elo_raw=away_elo,
                        post_match_elo_raw=away_post_elo,
                        pre_match_strength=self._calculator.normalize(away_elo),
                        post_match_strength=self._calculator.normalize(away_post_elo),
                        model_version=source,
                        seed_source=seed_source_by_team.get(
                            fixture.away_team_id, "legacy_projection"
                        ),
                    ),
                ))
                elo_by_team[fixture.home_team_id] = home_post_elo
                elo_by_team[fixture.away_team_id] = away_post_elo

            await self._repo.replace_fixture_team_strengths(
                season=season,
                participant_kind=resolved_kind,
                competition_ids=competition_ids,
                snapshots=snapshots,
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
                    elo_seed_raw=(seed_by_team.get(team_id) if use_seed_baseline else None),
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
