from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from sfa.domain.player_name_aliases import normalize_search_name
from sfa.infrastructure.models.player_name_aliases import PlayerNameAlias
from sfa.infrastructure.models.players.models import Player


class PlayerNameAliasRepository:
    def __init__(self, session):
        self._session = session

    async def find_player_id(self, external_id):
        return await self._session.scalar(select(Player.id).where(Player.external_id == external_id))

    async def add_aliases(self, player_id, external_id, aliases, *, provider, source_ref, captured_at):
        actual = await self.find_player_id(external_id)
        if actual != player_id:
            raise ValueError("Player alias crosswalk mismatch")
        rows = [{"player_id": player_id, "external_player_id": external_id, "provider": provider,
                 "alias": alias, "normalized_alias": normalize_search_name(alias),
                 "source_ref": source_ref, "captured_at": captured_at} for alias in aliases]
        if not rows:
            return 0
        added = await self._session.execute(insert(PlayerNameAlias).values(rows).on_conflict_do_nothing(
            constraint="uq_player_name_alias").returning(PlayerNameAlias.id))
        return len(added.scalars().all())
