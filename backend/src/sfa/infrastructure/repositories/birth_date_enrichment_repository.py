from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.enrichment.birth_date_ports import BirthDateEnrichmentRepositoryPort
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.teams.models import Team

logger = logging.getLogger(__name__)


class BirthDateEnrichmentRepository(BirthDateEnrichmentRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_teams_for_birth_date_refresh(
        self,
        season: str,
    ) -> list[tuple[int, int]]:
        """Return distinct teams that have player stats in the requested season."""
        stmt = (
            select(Team.external_id, PlayerStats.season)
            .join(Team, PlayerStats.team_id == Team.id)
            .where(
                PlayerStats.season == season,
                Team.external_id.is_not(None),
            )
            .group_by(Team.external_id, PlayerStats.season)
        )
        rows = (await self._session.execute(stmt)).all()
        return self._parse_team_seasons(rows)

    async def get_teams_missing_birth_date(
        self,
        season: str,
    ) -> list[tuple[int, int]]:
        """Return distinct (team_external_id, season_int) where any player lacks birth_date."""
        stmt = (
            select(Team.external_id, PlayerStats.season)
            .join(Player, PlayerStats.player_id == Player.id)
            .join(Team, PlayerStats.team_id == Team.id)
            .where(
                PlayerStats.season == season,
                Player.birth_date.is_(None),
                Team.external_id.is_not(None),
            )
            .group_by(Team.external_id, PlayerStats.season)
        )
        rows = (await self._session.execute(stmt)).all()
        return self._parse_team_seasons(rows)

    async def get_players_missing_birth_date(
        self,
        season: str,
    ) -> list[tuple[int, int]]:
        """Return players still missing birth_date after squad-level refresh."""
        stmt = (
            select(Player.external_id, PlayerStats.season)
            .join(PlayerStats, PlayerStats.player_id == Player.id)
            .where(
                PlayerStats.season == season,
                Player.external_id.is_not(None),
                Player.birth_date.is_(None),
            )
            .group_by(Player.external_id, PlayerStats.season)
        )
        rows = (await self._session.execute(stmt)).all()
        result: list[tuple[int, int]] = []
        for player_ext_id, season_str in rows:
            try:
                result.append((int(player_ext_id), int(season_str)))
            except (TypeError, ValueError):
                logger.warning(
                    "[BirthDateEnrichmentRepository] Skipping unparseable player=%r season=%r",
                    player_ext_id,
                    season_str,
                )
        return result

    def _parse_team_seasons(self, rows) -> list[tuple[int, int]]:
        result = []
        for team_ext_id, season_str in rows:
            try:
                result.append((int(team_ext_id), int(season_str)))
            except (TypeError, ValueError):
                logger.warning(
                    "[BirthDateEnrichmentRepository] Skipping unparseable season=%r team=%r",
                    season_str,
                    team_ext_id,
                )
        return result

    async def upsert_player_birth_date(
        self,
        external_id: int,
        birth_date: date | None,
        force_update: bool = False,
    ) -> int:
        conditions = [Player.external_id == external_id]
        if not force_update:
            conditions.append(Player.birth_date.is_(None))

        stmt = update(Player).where(*conditions).values(birth_date=birth_date)
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)

    async def count_players_missing_birth_date(self) -> int:
        stmt = select(func.count()).where(
            Player.external_id.is_not(None),
            Player.birth_date.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
