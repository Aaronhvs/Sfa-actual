from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.transfermarkt_ports import PlayerTmIdRepositoryPort, PlayerTmIdRow
from sfa.infrastructure.models.player_tm_ids.models import PlayerTmId


class PlayerTmIdRepository(PlayerTmIdRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_tm_id(self, player_id: int) -> PlayerTmIdRow | None:
        stmt = select(PlayerTmId).where(PlayerTmId.player_id == player_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return PlayerTmIdRow(player_id=row.player_id, tm_id=row.tm_id, verified=row.verified)

    async def upsert_tm_id(self, player_id: int, tm_id: int, verified: bool) -> None:
        stmt = (
            pg_insert(PlayerTmId)
            .values(player_id=player_id, tm_id=tm_id, verified=verified)
            .on_conflict_do_update(
                index_elements=["player_id"],
                set_={"tm_id": tm_id, "verified": verified},
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
