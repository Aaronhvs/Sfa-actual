from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol
from sfa.infrastructure.models.scores.models import SFASeasonScore


class SeasonRepository(SeasonRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_available_seasons(self) -> list[SeasonDTO]:
        stmt = (
            select(SFASeasonScore.season)
            .distinct()
            .order_by(SFASeasonScore.season.desc())
        )
        seasons = list((await self._session.execute(stmt)).scalars().all())
        latest = seasons[0] if seasons else None
        return [
            SeasonDTO(season=season, is_latest=(season == latest))
            for season in seasons
        ]
