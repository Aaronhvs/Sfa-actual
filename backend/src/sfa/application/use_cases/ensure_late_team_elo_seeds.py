from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timezone

from sfa.domain.scoring_ports import (
    EloSeedProvenanceDTO,
    TeamEloSeedDTO,
    TeamStrengthRepositoryPort,
)

logger = logging.getLogger(__name__)

LATE_ENTRY_DEFAULT_ELO = 1000.0


@dataclass(frozen=True)
class EnsureLateTeamEloSeedsResult:
    season: str
    participant_kind: str
    rollover_created: int
    default_created: int
    status: str
    error: str | None


class EnsureLateTeamEloSeedsUseCase:
    """Create canonical seeds for teams discovered after season bootstrap."""

    def __init__(self, repo: TeamStrengthRepositoryPort) -> None:
        self._repo = repo

    async def execute(
        self,
        season: str,
        participant_kind: str,
        competition_ids: list[int],
    ) -> EnsureLateTeamEloSeedsResult:
        try:
            fixtures = await self._repo.get_fixtures_for_elo_recalc(
                season,
                competition_ids,
            )
            fixture_team_ids = {
                team_id
                for fixture in fixtures
                for team_id in (fixture.home_team_id, fixture.away_team_id)
            }
            existing_seeds = await self._repo.get_team_elo_seeds(
                season,
                participant_kind,
            )
            seeded_team_ids = {seed.team_id for seed in existing_seeds}
            missing_team_ids = sorted(fixture_team_ids - seeded_team_ids)
            if not missing_team_ids:
                return EnsureLateTeamEloSeedsResult(
                    season=season,
                    participant_kind=participant_kind,
                    rollover_created=0,
                    default_created=0,
                    status="completed",
                    error=None,
                )

            previous_season = _previous_season(season)
            previous_rows = await self._repo.get_all_teams_with_elo(previous_season)
            previous_elo_by_team = {row.team_id: row.elo_raw for row in previous_rows}
            effective_at = min(fixture.played_at for fixture in fixtures)
            if effective_at.tzinfo is None:
                effective_at = effective_at.replace(tzinfo=timezone.utc)

            rollover_created = 0
            default_created = 0
            for team_id in missing_team_ids:
                previous_elo = previous_elo_by_team.get(team_id)
                if previous_elo is None:
                    elo_raw = LATE_ENTRY_DEFAULT_ELO
                    source = "manual_override"
                    source_reference = "late-entry-policy:1000"
                    resolution_method = "late_entry_default"
                    reason = (
                        "Team entered the fixture pool after season bootstrap "
                        "and has no prior-season ELO"
                    )
                    default_created += 1
                else:
                    elo_raw = previous_elo
                    source = "season_rollover"
                    source_reference = f"season-rollover:{previous_season}"
                    resolution_method = "season_rollover"
                    reason = "Late entrant inherited its prior-season closing ELO"
                    rollover_created += 1

                await self._repo.upsert_team_elo_seed(
                    TeamEloSeedDTO(
                        team_id=team_id,
                        season=season,
                        participant_kind=participant_kind,
                        elo_raw=elo_raw,
                        effective_at=effective_at,
                        source=source,
                        source_reference=source_reference,
                        provenance=EloSeedProvenanceDTO(
                            resolution_method=resolution_method,
                            cutoff=effective_at.date(),
                            source_reference=source_reference,
                            reason=reason,
                            approved_by="season-bootstrap-policy",
                        ),
                    )
                )

            logger.info(
                "[EnsureLateTeamEloSeedsUseCase] season=%s kind=%s "
                "rollover_created=%d default_created=%d",
                season,
                participant_kind,
                rollover_created,
                default_created,
            )
            return EnsureLateTeamEloSeedsResult(
                season=season,
                participant_kind=participant_kind,
                rollover_created=rollover_created,
                default_created=default_created,
                status="completed",
                error=None,
            )
        except Exception as exc:
            logger.exception(
                "[EnsureLateTeamEloSeedsUseCase] Failed season=%s kind=%s",
                season,
                participant_kind,
            )
            return EnsureLateTeamEloSeedsResult(
                season=season,
                participant_kind=participant_kind,
                rollover_created=0,
                default_created=0,
                status="failed",
                error=str(exc),
            )


def _previous_season(season: str) -> str:
    if "-" in season and len(season) == 7:
        start = int(season[:4])
        return f"{start - 1}-{str(start - 1)[2:]}"
    if "/" in season and len(season) == 5:
        start = int(season[:2])
        return f"{start - 1:02d}/{start:02d}"
    return str(int(season) - 1)
