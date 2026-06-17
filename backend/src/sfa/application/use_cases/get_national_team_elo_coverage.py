from __future__ import annotations

from dataclasses import dataclass

from sfa.domain.scoring_ports import TeamStrengthCoverageRow, TeamStrengthRepositoryPort

WORLD_CUP_COMPETITION_NAME = "World Cup"


@dataclass(frozen=True)
class NationalTeamEloCoverageResult:
    season: str
    competition_id: int | None
    total_teams: int
    teams_with_strength: int
    missing: list[str]
    coverage_pct: float
    rows: list[TeamStrengthCoverageRow]
    status: str
    error: str | None


class GetNationalTeamEloCoverageUseCase:
    def __init__(self, repo: TeamStrengthRepositoryPort) -> None:
        self._repo = repo

    async def execute(
        self,
        season: str,
        competition_id: int | None = None,
    ) -> NationalTeamEloCoverageResult:
        resolved_competition_id = competition_id
        if resolved_competition_id is None:
            resolved_competition_id = await self._repo.get_competition_id_by_name(
                WORLD_CUP_COMPETITION_NAME
            )
        if resolved_competition_id is None:
            return NationalTeamEloCoverageResult(
                season=season,
                competition_id=None,
                total_teams=0,
                teams_with_strength=0,
                missing=[],
                coverage_pct=0.0,
                rows=[],
                status="failed",
                error="World Cup competition not found",
            )

        rows = await self._repo.get_team_strength_coverage(resolved_competition_id, season)
        total = len(rows)
        with_strength = sum(1 for row in rows if row.strength is not None)
        missing = sorted(row.team_name for row in rows if row.strength is None)
        coverage_pct = round((with_strength / total) * 100.0, 2) if total else 0.0
        return NationalTeamEloCoverageResult(
            season=season,
            competition_id=resolved_competition_id,
            total_teams=total,
            teams_with_strength=with_strength,
            missing=missing,
            coverage_pct=coverage_pct,
            rows=rows,
            status="completed",
            error=None,
        )
