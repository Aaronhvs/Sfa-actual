from __future__ import annotations

import asyncio
import logging
import re
import unicodedata

from sfa.domain.transfermarkt_ports import (
    EnrichPositionRepositoryPort,
    EnrichPositionsResult,
    PlayerTmIdRepositoryPort,
    TransfermarktProviderPort,
)

logger = logging.getLogger(__name__)


def _slugify_player_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


class EnrichPlayerPositionsUseCase:
    def __init__(
        self,
        provider: TransfermarktProviderPort,
        tm_id_repo: PlayerTmIdRepositoryPort,
        enrich_repo: EnrichPositionRepositoryPort,
        rate_limit_seconds: float = 1.0,
    ) -> None:
        self._provider = provider
        self._tm_id_repo = tm_id_repo
        self._enrich_repo = enrich_repo
        self._rate_limit_seconds = rate_limit_seconds

    async def execute(self, batch_size: int = 500) -> EnrichPositionsResult:
        players = await self._enrich_repo.get_players_without_tm_source(batch_size)
        matched = 0
        position_updated = 0
        unmatched = 0
        failed = 0
        skipped_already_tm = 0

        for player in players:
            if player.position_source == "transfermarkt":
                skipped_already_tm += 1
                continue

            try:
                cached = await self._tm_id_repo.get_tm_id(player.id)
                if cached is not None:
                    tm_id = cached.tm_id
                    slug = _slugify_player_name(player.name)
                else:
                    search = await self._provider.search_player(player.name, player.team_name)
                    await asyncio.sleep(self._rate_limit_seconds)
                    if search is None:
                        unmatched += 1
                        continue
                    tm_id = search.tm_id
                    slug = search.slug
                    await self._tm_id_repo.upsert_tm_id(player.id, tm_id, verified=False)

                tm_data = await self._provider.fetch_player_position(tm_id, slug)
                await asyncio.sleep(self._rate_limit_seconds)
                if tm_data is None:
                    unmatched += 1
                    continue

                matched += 1
                await self._enrich_repo.update_player_position(
                    player.id, tm_data.position_mapped, "transfermarkt"
                )
                position_updated += 1
                logger.info(
                    "[EnrichPlayerPositionsUseCase] Updated player_id=%s name=%s raw_position=%s",
                    player.id, player.name, tm_data.position_raw,
                )
            except Exception as exc:
                failed += 1
                logger.error(
                    "[EnrichPlayerPositionsUseCase] Failed player_id=%s name=%s: %s",
                    player.id, player.name, exc,
                )

        logger.info(
            "[EnrichPlayerPositionsUseCase] Done total=%s matched=%s updated=%s unmatched=%s failed=%s skipped=%s",
            len(players), matched, position_updated, unmatched, failed, skipped_already_tm,
        )
        return EnrichPositionsResult(
            total_processed=len(players),
            matched=matched,
            position_updated=position_updated,
            unmatched=unmatched,
            failed=failed,
            skipped_already_tm=skipped_already_tm,
        )
