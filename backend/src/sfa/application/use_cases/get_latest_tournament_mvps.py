from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.matchday_mvp import FEATURED_NAMES, MatchdayMvp, TournamentMvpReaderProtocol, competition_key
from sfa.domain.ports import TournamentCompetitionDTO, TournamentRepositoryProtocol


@dataclass(frozen=True)
class LatestTournamentMvp:
    competition: TournamentCompetitionDTO
    mvp: MatchdayMvp


@dataclass(frozen=True)
class GetLatestTournamentMvpsResult:
    season: str
    items: tuple[LatestTournamentMvp, ...]


@runtime_checkable
class GetLatestTournamentMvpsUseCaseProtocol(Protocol):
    async def execute(self, season: str | None = None) -> GetLatestTournamentMvpsResult: ...


class GetLatestTournamentMvpsUseCase(GetLatestTournamentMvpsUseCaseProtocol):
    def __init__(self, tournaments: TournamentRepositoryProtocol, mvps: TournamentMvpReaderProtocol) -> None:
        self._tournaments, self._mvps = tournaments, mvps

    async def execute(self, season: str | None = None) -> GetLatestTournamentMvpsResult:
        season = season or await self._tournaments.resolve_latest_season() or ""
        competitions = await self._tournaments.list_competitions(season)
        featured = [c for c in competitions if competition_key(c.name) in FEATURED_NAMES and c.completed_fixtures > 0]
        featured.sort(key=lambda c: (FEATURED_NAMES.index(competition_key(c.name)), c.id))
        items = []
        for competition in featured:
            mvps = await self._mvps.get_items(competition, season)
            if mvps:
                items.append(LatestTournamentMvp(competition, mvps[-1]))
        return GetLatestTournamentMvpsResult(season, tuple(items))
