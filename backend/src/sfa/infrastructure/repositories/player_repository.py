from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import PlayerDTO, PlayerRepositoryProtocol
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.teams.models import Team


class PlayerRepository(PlayerRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, player_id: int) -> PlayerDTO | None:
        latest_team = (
            select(
                PlayerStats.player_id,
                PlayerStats.team_id,
                func.row_number().over(
                    partition_by=PlayerStats.player_id,
                    order_by=(
                        Fixture.played_at.desc(),
                        Fixture.id.desc(),
                        PlayerStats.id.desc(),
                    ),
                ).label("rn"),
            )
            .join(Fixture, Fixture.id == PlayerStats.fixture_id)
            .where(PlayerStats.team_id.is_not(None))
            .where(
                (PlayerStats.team_id == Fixture.home_team_id)
                | (PlayerStats.team_id == Fixture.away_team_id)
            )
            .subquery()
        )
        stmt = (
            select(
                Player.id, Player.name, Player.position,
                Player.photo_url,
                Team.name.label("team_name"),
            )
            .join(
                latest_team,
                (latest_team.c.player_id == Player.id) & (latest_team.c.rn == 1),
            )
            .join(Team, latest_team.c.team_id == Team.id)
            .where(Player.id == player_id)
        )
        row = (await self._session.execute(stmt)).mappings().first()
        if row is None:
            return None
        return PlayerDTO(
            id=row["id"],
            name=row["name"],
            position=str(row["position"]),
            photo_url=row["photo_url"],
            team_name=row["team_name"],
        )

    async def exists(self, player_id: int) -> bool:
        stmt = select(Player.id).where(Player.id == player_id).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None
