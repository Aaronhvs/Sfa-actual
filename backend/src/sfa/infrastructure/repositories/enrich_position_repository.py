from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.transfermarkt_ports import EnrichPositionRepositoryPort, PlayerForEnrichDTO
from sfa.infrastructure.models.enums import Position
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.teams.models import Team


class EnrichPositionRepository(EnrichPositionRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_players_without_tm_source(self, limit: int) -> list[PlayerForEnrichDTO]:
        latest_team = (
            select(
                PlayerStats.player_id,
                PlayerStats.team_id,
                func.row_number().over(
                    partition_by=PlayerStats.player_id,
                    order_by=PlayerStats.fixture_id.desc(),
                ).label("rn"),
            )
            .where(PlayerStats.team_id.is_not(None))
            .subquery()
        )
        stmt = (
            select(
                Player.id,
                Player.name,
                Team.name.label("team_name"),
                Player.position_source,
            )
            .join(
                latest_team,
                (latest_team.c.player_id == Player.id) & (latest_team.c.rn == 1),
            )
            .join(Team, latest_team.c.team_id == Team.id)
            .where(Player.position_source != "transfermarkt")
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            PlayerForEnrichDTO(
                id=row["id"],
                name=row["name"],
                team_name=row["team_name"],
                position_source=row["position_source"],
            )
            for row in rows
        ]

    async def update_player_position(
        self, player_id: int, position: Position, source: str,
    ) -> None:
        stmt = (
            update(Player)
            .where(Player.id == player_id)
            .values(position=position, position_source=source)
        )
        await self._session.execute(stmt)
        await self._session.flush()
