from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.matchday_mvp import (
    POLICY_VERSION,
    MatchdayMvp,
    MatchdayMvpCacheProtocol,
    MatchdayMvpRepositoryProtocol,
    TournamentMvpReaderProtocol,
    group_rounds,
    select_mvps,
)
from sfa.domain.player_leads.ports import ScopeRulesVersionResolverProtocol
from sfa.domain.ports import SeasonRepositoryProtocol, TournamentCompetitionDTO, TournamentRepositoryProtocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GetTournamentMvpsResult:
    competition_id: int
    season: str
    items: tuple[MatchdayMvp, ...]


@runtime_checkable
class GetTournamentMvpsUseCaseProtocol(Protocol):
    async def execute(self, competition_id: int, season: str | None = None) -> GetTournamentMvpsResult: ...


class GetTournamentMvpsUseCase(GetTournamentMvpsUseCaseProtocol, TournamentMvpReaderProtocol):
    def __init__(self, repository: MatchdayMvpRepositoryProtocol, tournaments: TournamentRepositoryProtocol,
                 seasons: SeasonRepositoryProtocol, rules: ScopeRulesVersionResolverProtocol,
                 cache: MatchdayMvpCacheProtocol, default_rules_version_id: int | None = None) -> None:
        self._repository, self._tournaments, self._seasons = repository, tournaments, seasons
        self._rules, self._cache, self._default_version = rules, cache, default_rules_version_id
        self._contexts = {}

    async def execute(self, competition_id: int, season: str | None = None) -> GetTournamentMvpsResult:
        if not await self._repository.competition_exists(competition_id):
            raise ValueError("Competition not found")
        season = season or await self._tournaments.resolve_latest_season() or ""
        competitions = await self._tournaments.list_competitions(season)
        competition = next((c for c in competitions if c.id == competition_id), None)
        items = await self.get_items(competition, season) if competition else ()
        return GetTournamentMvpsResult(competition_id, season, items)

    async def get_items(self, competition: TournamentCompetitionDTO, season: str) -> tuple[MatchdayMvp, ...]:
        if season not in self._contexts:
            available = await self._seasons.get_available_seasons()
            key = next((s.key for s in available if s.key == f"season-{season}"), None)
            scope = await self._seasons.resolve_scope(key) if key else None
            version = None
            if scope:
                version = await self._rules.resolve_rules_version_id_for_scope(scope, self._default_version)
            self._contexts[season] = scope, version
        scope, version = self._contexts[season]
        if scope is None or (season, competition.id) not in scope.pairs:
            return ()
        stamp = await self._repository.get_data_stamp(scope, competition.id, season, version)
        key = f"{POLICY_VERSION}:{competition.id}:{season}:{scope.key}:{version}:{stamp}"
        cached = await self._cache.read(key)
        if cached is not None:
            return cached
        fixtures = await self._repository.get_fixtures(competition.id, season)
        rounds = group_rounds(competition.name, fixtures)
        included = {f.id for group in rounds for f in group.fixtures}
        excluded = len(fixtures) - len(included)
        if excluded:
            logger.info("[GetTournamentMvpsUseCase] Unsupported round metadata competition=%s season=%s fixtures=%s",
                        competition.id, season, excluded)
        performances = await self._repository.get_performances(competition.id, season, version)
        positions = await self._repository.get_positions(scope, competition.id)
        items = select_mvps(rounds, performances, positions)
        # Optimistic validation: never cache inputs that changed during the read.
        if stamp == await self._repository.get_data_stamp(scope, competition.id, season, version):
            await self._cache.write(key, items)
        return items
