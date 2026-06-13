from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.transfermarkt_ports import EnrichPositionRepositoryPort, PlayerForEnrichDTO
from sfa.infrastructure.models.enums import Position
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.teams.models import Team


class EnrichPositionRepository(EnrichPositionRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_players_without_tm_source(self, limit: int) -> list[PlayerForEnrichDTO]:
        stmt = (
            select(
                Player.id,
                Player.name,
                Team.name.label("team_name"),
                Player.position_source,
            )
            .join(Team, Player.team_id == Team.id)
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
