from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.enrichment.birth_date_ports import (
    BirthDateEnrichmentRepositoryPort,
    PlayerBirthDateProviderPort,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnrichPlayerBirthDatesResult:
    teams_processed: int
    players_updated: int
    players_skipped: int
    status: str
    error: str | None


class EnrichPlayerBirthDatesUseCase:
    def __init__(
        self,
        provider: PlayerBirthDateProviderPort,
        repo: BirthDateEnrichmentRepositoryPort,
    ) -> None:
        self._provider = provider
        self._repo = repo

    async def execute(
        self,
        season: str,
        force_update: bool = False,
    ) -> EnrichPlayerBirthDatesResult:
        logger.info(
            "[EnrichPlayerBirthDatesUseCase] Starting enrichment season=%s force_update=%s",
            season,
            force_update,
        )

        if force_update:
            team_pairs = await self._repo.get_teams_for_birth_date_refresh(season)
        else:
            team_pairs = await self._repo.get_teams_missing_birth_date(season)

        teams_processed = 0
        players_updated = 0
        players_skipped = 0

        for team_external_id, season_int in team_pairs:
            try:
                birth_dates = await self._provider.fetch_squad_birth_dates(
                    team_id=team_external_id,
                    season=season_int,
                )
                for dto in birth_dates:
                    if dto.birth_date is not None or force_update:
                        updated = await self._repo.upsert_player_birth_date(
                            dto.external_id,
                            dto.birth_date,
                            force_update=force_update,
                        )
                        if updated:
                            players_updated += updated
                        else:
                            players_skipped += 1
                    else:
                        players_skipped += 1
                teams_processed += 1
                logger.info(
                    "[EnrichPlayerBirthDatesUseCase] team_id=%d season=%d — %d players processed",
                    team_external_id,
                    season_int,
                    len(birth_dates),
                )
            except Exception as exc:
                logger.error(
                    "[EnrichPlayerBirthDatesUseCase] Failed for team_id=%d season=%d: %s",
                    team_external_id,
                    season_int,
                    exc,
                )

        for player_external_id, season_int in await self._repo.get_players_missing_birth_date(season):
            try:
                dto = await self._provider.fetch_player_birth_date(
                    player_id=player_external_id,
                    season=season_int,
                )
                if dto is None:
                    players_skipped += 1
                    continue
                if dto.birth_date is not None or force_update:
                    updated = await self._repo.upsert_player_birth_date(
                        dto.external_id,
                        dto.birth_date,
                        force_update=force_update,
                    )
                    if updated:
                        players_updated += updated
                    else:
                        players_skipped += 1
                else:
                    players_skipped += 1
            except Exception as exc:
                players_skipped += 1
                logger.error(
                    "[EnrichPlayerBirthDatesUseCase] Failed individual player_id=%d season=%d: %s",
                    player_external_id,
                    season_int,
                    exc,
                )

        missing_after = await self._repo.count_players_missing_birth_date()
        logger.info(
            "[EnrichPlayerBirthDatesUseCase] Done. teams=%d updated=%d skipped=%d still_missing=%d",
            teams_processed,
            players_updated,
            players_skipped,
            missing_after,
        )

        return EnrichPlayerBirthDatesResult(
            teams_processed=teams_processed,
            players_updated=players_updated,
            players_skipped=players_skipped,
            status="completed",
            error=None,
        )
