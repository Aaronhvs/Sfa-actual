from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring_ports import TeamStrengthRepositoryPort

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

    async def execute(self, date_str: str, season: str) -> SeedClubEloResult:
        try:
            snapshot = await self._provider.fetch_snapshot(date_str)
            team_name_id_map = await self._repo.get_team_name_id_map(season)
            sfa_team_names = list(team_name_id_map.keys())
            matched = 0
            unmatched: list[str] = []

            for entry in snapshot:
                if entry.level != 1:
                    continue

                sfa_name = self._provider.resolve_team_name(entry.club_name, sfa_team_names)
                if sfa_name is None:
                    unmatched.append(entry.club_name)
                    continue

                team_id = team_name_id_map[sfa_name]
                competition_ids = await self._repo.get_active_competition_ids_for_team(team_id, season)
                strength = self._calculator.normalize(entry.elo)
                await self._repo.upsert_team_elo(
                    team_id=team_id,
                    season=season,
                    elo_raw=entry.elo,
                    strength_normalized=strength,
                    source="clubelo_seed",
                    competition_ids=competition_ids,
                )
                matched += 1

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
