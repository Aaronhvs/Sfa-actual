from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScopeNotFoundError, ScoreSource
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.scores.models import SFASeasonScore

WORLD_CUP_NAME = "World Cup"
WORLD_CUP_AWARD_SEASON = "2025"
WORLD_CUP_PHYSICAL_SEASON = "2026"


class SeasonRepository(SeasonRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_scopes(self) -> list[AwardPeriodScope]:
        stmt = (
            select(
                SFASeasonScore.season,
                SFASeasonScore.competition_id,
                Competition.name,
                Competition.participant_kind,
            )
            .join(Competition, Competition.id == SFASeasonScore.competition_id)
            .distinct()
        )
        rows = (await self._session.execute(stmt)).all()
        club_competitions: dict[str, set[int]] = defaultdict(set)
        world_cups: dict[str, int] = {}
        for season, competition_id, name, participant_kind in rows:
            if participant_kind == "club":
                club_competitions[str(season)].add(int(competition_id))
            elif name == WORLD_CUP_NAME:
                world_cups[str(season)] = int(competition_id)

        latest_club_season = max(club_competitions, key=_season_sort_key, default=None)
        scopes: list[AwardPeriodScope] = []
        for season in sorted(club_competitions, key=_season_sort_key):
            sources = [ScoreSource(season, tuple(club_competitions[season]))]
            includes_world_cup = False
            if season == WORLD_CUP_AWARD_SEASON and WORLD_CUP_PHYSICAL_SEASON in world_cups:
                sources.append(
                    ScoreSource(
                        WORLD_CUP_PHYSICAL_SEASON,
                        (world_cups[WORLD_CUP_PHYSICAL_SEASON],),
                    )
                )
                includes_world_cup = True
            scopes.append(
                AwardPeriodScope(
                    key=f"season-{season}",
                    label=_club_season_label(season),
                    kind=ScopeKind.AWARD_PERIOD,
                    sources=tuple(sources),
                    is_latest=(season == latest_club_season),
                    includes_world_cup=includes_world_cup,
                )
            )

        for season in sorted(world_cups, key=_season_sort_key):
            scopes.append(
                AwardPeriodScope(
                    key=f"world-cup-{season}",
                    label=f"Mundial {season}",
                    kind=ScopeKind.TOURNAMENT,
                    sources=(ScoreSource(season, (world_cups[season],)),),
                    includes_world_cup=True,
                )
            )
        return scopes

    async def get_available_seasons(self) -> list[SeasonDTO]:
        scopes = await self._get_scopes()
        return self._to_dtos(scopes)

    async def get_available_scopes_for_player(self, player_id: int) -> list[SeasonDTO]:
        rows = (
            await self._session.execute(
                select(SFASeasonScore.season, SFASeasonScore.competition_id)
                .where(SFASeasonScore.player_id == player_id)
                .distinct()
            )
        ).all()
        player_pairs = {(str(season), int(competition_id)) for season, competition_id in rows}
        scopes = [
            scope for scope in await self._get_scopes()
            if scope.pairs.intersection(player_pairs)
        ]
        return self._to_dtos(scopes)

    @staticmethod
    def _to_dtos(scopes: list[AwardPeriodScope]) -> list[SeasonDTO]:
        return [
            SeasonDTO(
                season=scope.sources[0].season,
                is_latest=scope.is_latest,
                is_world_cup=(scope.kind == ScopeKind.TOURNAMENT),
                key=scope.key,
                label=scope.label,
                kind=scope.kind.value,
                includes_world_cup=scope.includes_world_cup,
            )
            for scope in sorted(scopes, key=_scope_sort_key, reverse=True)
        ]

    async def resolve_scope(self, scope_key: str | None = None) -> AwardPeriodScope | None:
        scopes = await self._get_scopes()
        if scope_key is None:
            return next((scope for scope in scopes if scope.is_latest), None)
        scope = next((item for item in scopes if item.key == scope_key), None)
        if scope is None:
            raise ScopeNotFoundError(scope_key)
        return scope


def _season_sort_key(season: str) -> tuple[int, str]:
    try:
        return int(season[:4]), season
    except ValueError:
        return -1, season


def _scope_sort_key(scope: AwardPeriodScope) -> tuple[int, int]:
    season_key = _season_sort_key(scope.sources[0].season)[0]
    tournament_priority = 0 if scope.kind == ScopeKind.TOURNAMENT else 1
    return season_key, tournament_priority


def _club_season_label(season: str) -> str:
    try:
        year = int(season[:4])
    except ValueError:
        return season
    return f"{year}/{year + 1}"
