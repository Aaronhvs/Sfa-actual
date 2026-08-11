from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sfa.domain.scoring_ports import (
    ManualClubEloEntry,
    TeamEloSeedDTO,
    TeamStrengthRepositoryPort,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedClubEloResult:
    date_str: str
    season: str
    matched: int
    unmatched: list[str]
    status: str
    error: str | None


class SeedClubEloUseCase:
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
        date_str: str,
        season: str,
        manual_entries: list[ManualClubEloEntry] | None = None,
    ) -> SeedClubEloResult:
        try:
            snapshot = await self._provider.fetch_snapshot(date_str)
            team_name_id_map = await self._repo.get_team_name_id_map(season, "club")
            sfa_team_names = list(team_name_id_map.keys())
            seeds_by_team: dict[str, tuple[float, str, str]] = {}

            for entry in snapshot:
                sfa_name = self._provider.resolve_team_name(entry.club_name, sfa_team_names)
                if sfa_name is not None and sfa_name not in seeds_by_team:
                    seeds_by_team[sfa_name] = (entry.elo, "clubelo", date_str)

            for manual_entry in manual_entries or []:
                if manual_entry.team_name in team_name_id_map:
                    seeds_by_team[manual_entry.team_name] = (
                        manual_entry.elo_raw,
                        "manual_override",
                        manual_entry.reason,
                    )

            unmatched = sorted(set(sfa_team_names) - set(seeds_by_team))
            if unmatched:
                return SeedClubEloResult(
                    date_str=date_str,
                    season=season,
                    matched=len(seeds_by_team),
                    unmatched=unmatched,
                    status="failed",
                    error=f"Missing ClubElo seed for {len(unmatched)} active teams",
                )

            effective_at = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            for sfa_name, seed_data in seeds_by_team.items():
                elo_raw, seed_source, source_reference = seed_data
                team_id = team_name_id_map[sfa_name]
                competition_ids = await self._repo.get_active_competition_ids_for_team(team_id, season)
                strength = self._calculator.normalize(elo_raw)
                await self._repo.upsert_team_elo_seed(
                    TeamEloSeedDTO(
                        team_id=team_id,
                        season=season,
                        participant_kind="club",
                        elo_raw=elo_raw,
                        effective_at=effective_at,
                        source=seed_source,
                        source_reference=source_reference,
                    )
                )
                await self._repo.upsert_team_elo(
                    team_id=team_id,
                    season=season,
                    elo_raw=elo_raw,
                    strength_normalized=strength,
                    source="clubelo_seed",
                    competition_ids=competition_ids,
                    elo_seed_raw=elo_raw,
                )

            matched = len(seeds_by_team)

            logger.info(
                "[SeedClubEloUseCase] date=%s season=%s matched=%d unmatched=%d",
                date_str,
                season,
                matched,
                len(unmatched),
            )
            return SeedClubEloResult(
                date_str=date_str,
                season=season,
                matched=matched,
                unmatched=unmatched,
                status="completed",
                error=None,
            )
        except Exception as exc:
            logger.error("[SeedClubEloUseCase] Failed date=%s season=%s: %s", date_str, season, exc)
            return SeedClubEloResult(
                date_str=date_str,
                season=season,
                matched=0,
                unmatched=[],
                status="failed",
                error=str(exc),
            )
