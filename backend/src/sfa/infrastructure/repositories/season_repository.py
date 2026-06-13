from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
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

        wc_seasons: set[str] = set()
        if seasons:
            wc_stmt = (
                select(Fixture.season)
                .distinct()
                .join(Competition, Competition.id == Fixture.competition_id)
                .where(
                    Competition.participant_kind == "national_team",
                    Fixture.season.in_(seasons),
                )
            )
            wc_seasons = set((await self._session.execute(wc_stmt)).scalars().all())

        return [
            SeasonDTO(
                season=season,
                is_latest=(season == latest),
                is_world_cup=(season in wc_seasons),
            )
            for season in seasons
        ]
