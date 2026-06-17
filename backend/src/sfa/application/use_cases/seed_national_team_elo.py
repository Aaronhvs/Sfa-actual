from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring_ports import NationalTeamEloEntry, TeamStrengthRepositoryPort

logger = logging.getLogger(__name__)

NATIONAL_ELO_SOURCE = "national_elo_seed"
WORLD_CUP_COMPETITION_NAME = "World Cup"


@dataclass(frozen=True)
class SeedNationalTeamEloResult:
    season: str
    competition_id: int | None
    matched: int
    total_teams: int
    coverage_pct: float
    unmatched: list[str]
    source_date: str | None
    dry_run: bool
    status: str
    error: str | None


class SeedNationalTeamEloUseCase:
    def __init__(
        self,
        repo: TeamStrengthRepositoryPort,
        provider,
        calculator,
    ) -> None:
        self._repo = repo
        self._provider = provider
        self._calculator = calculator

    async def execute(
        self,
        season: str,
        competition_id: int | None = None,
        source_url: str | None = None,
        dry_run: bool = True,
        min_coverage: float = 100.0,
        manual_entries: list[NationalTeamEloEntry] | None = None,
    ) -> SeedNationalTeamEloResult:
        try:
            resolved_competition_id = competition_id
            if resolved_competition_id is None:
                resolved_competition_id = await self._repo.get_competition_id_by_name(
                    WORLD_CUP_COMPETITION_NAME
                )
            if resolved_competition_id is None:
                return self._failed(season, None, dry_run, "World Cup competition not found")

            teams = await self._repo.get_teams_for_competition_season(
                resolved_competition_id, season
            )
            if not teams:
                return self._failed(
                    season,
                    resolved_competition_id,
                    dry_run,
                    "No active World Cup teams found for season",
                )

            snapshot = await self._provider.fetch_snapshot(source_url, manual_entries=manual_entries)
            source_date = snapshot[0].source_date if snapshot else None
            team_names = [team.team_name for team in teams]
            entries_by_team: dict[str, NationalTeamEloEntry] = {}
            for entry in snapshot:
                team_name = self._provider.resolve_team_name(entry.country_name, team_names)
                if team_name is not None and team_name not in entries_by_team:
                    entries_by_team[team_name] = entry

            unmatched = sorted(
                team.team_name
                for team in teams
                if team.team_name not in entries_by_team
            )
            matched = len(teams) - len(unmatched)
            coverage_pct = round((matched / len(teams)) * 100.0, 2)

            if coverage_pct < min_coverage:
                return SeedNationalTeamEloResult(
                    season=season,
                    competition_id=resolved_competition_id,
                    matched=matched,
                    total_teams=len(teams),
                    coverage_pct=coverage_pct,
                    unmatched=unmatched,
                    source_date=source_date,
                    dry_run=dry_run,
                    status="failed",
                    error=f"Coverage {coverage_pct}% below required {min_coverage}%",
                )

            if not dry_run:
                for team in teams:
                    entry = entries_by_team[team.team_name]
                    await self._repo.upsert_team_elo(
                        team_id=team.team_id,
                        season=season,
                        elo_raw=entry.elo_raw,
                        strength_normalized=self._calculator.normalize(entry.elo_raw),
                        source=NATIONAL_ELO_SOURCE,
                        competition_ids=[resolved_competition_id],
                    )

            logger.info(
                "[SeedNationalTeamEloUseCase] season=%s competition_id=%s matched=%d "
                "total=%d dry_run=%s",
                season,
                resolved_competition_id,
                matched,
                len(teams),
                dry_run,
            )
            return SeedNationalTeamEloResult(
                season=season,
                competition_id=resolved_competition_id,
                matched=matched,
                total_teams=len(teams),
                coverage_pct=coverage_pct,
                unmatched=unmatched,
                source_date=source_date,
                dry_run=dry_run,
                status="completed",
                error=None,
            )
        except Exception as exc:
            logger.error("[SeedNationalTeamEloUseCase] Failed season=%s: %s", season, exc)
            return self._failed(season, competition_id, dry_run, str(exc))

    @staticmethod
    def _failed(
        season: str,
        competition_id: int | None,
        dry_run: bool,
        error: str,
    ) -> SeedNationalTeamEloResult:
        return SeedNationalTeamEloResult(
            season=season,
            competition_id=competition_id,
            matched=0,
            total_teams=0,
            coverage_pct=0.0,
            unmatched=[],
            source_date=None,
            dry_run=dry_run,
            status="failed",
            error=error,
        )
