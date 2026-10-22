from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.player_leads import (
    PlayerLead,
    PlayerLeadsCacheProtocol,
    PlayerLeadsCalculator,
    PlayerLeadsRepositoryProtocol,
    PlayerLeadsSnapshot,
    ScopeRulesVersionResolverProtocol,
)
from sfa.domain.ports import SeasonRepositoryProtocol
from sfa.domain.season_scope import AwardPeriodScope, InconsistentScopeRulesVersionError, ScopeKind

logger = logging.getLogger(__name__)

ALL_SCOPE_KEY = "all"


@dataclass(frozen=True)
class GetPlayerLeadsResult:
    player_id: int
    scope_key: str | None
    scope_label: str | None
    supported: bool
    policy_version: str
    rules_version_id: int | None
    items: tuple[PlayerLead, ...]


@runtime_checkable
class GetPlayerLeadsUseCaseProtocol(Protocol):
    async def execute(
        self, player_id: int, scope_key: str | None = None, max_rank: int = 3, limit: int = 3,
    ) -> GetPlayerLeadsResult: ...


class GetPlayerLeadsUseCase(GetPlayerLeadsUseCaseProtocol):
    def __init__(
        self,
        season_repo: SeasonRepositoryProtocol,
        rules_resolver: ScopeRulesVersionResolverProtocol,
        leads_repo: PlayerLeadsRepositoryProtocol,
        cache: PlayerLeadsCacheProtocol,
        calculator: PlayerLeadsCalculator,
    ) -> None:
        self._season_repo = season_repo
        self._rules_resolver = rules_resolver
        self._leads_repo = leads_repo
        self._cache = cache
        self._calculator = calculator

    async def execute(
        self, player_id: int, scope_key: str | None = None, max_rank: int = 3, limit: int = 3,
    ) -> GetPlayerLeadsResult:
        policy = self._calculator.policy
        policy.validate_request(max_rank, limit)

        if scope_key == ALL_SCOPE_KEY:
            return self._empty(player_id, ALL_SCOPE_KEY, None, supported=False, rules_version_id=None)
        scope = await self._season_repo.resolve_scope(scope_key)
        if scope is None:
            return self._empty(player_id, None, None, supported=True, rules_version_id=None)
        if scope.kind == ScopeKind.ALL_TIME:
            return self._empty(player_id, scope.key, scope.label, supported=False, rules_version_id=None)

        try:
            rules_version_id: int | None = await self._rules_resolver.resolve_rules_version_id_for_scope(scope)
        except InconsistentScopeRulesVersionError:
            logger.warning("[GetPlayerLeadsUseCase] Inconsistent rules version for %s, SFA metric skipped", scope.key)
            rules_version_id = None

        leads = await self._leads_for(scope, rules_version_id, player_id)
        items = tuple(lead for lead in leads if lead.rank <= max_rank)[:limit]
        return GetPlayerLeadsResult(
            player_id=player_id,
            scope_key=scope.key,
            scope_label=scope.label,
            supported=True,
            policy_version=policy.policy_version,
            rules_version_id=rules_version_id,
            items=items,
        )

    async def _leads_for(
        self, scope: AwardPeriodScope, rules_version_id: int | None, player_id: int,
    ) -> tuple[PlayerLead, ...]:
        stamp = await self._leads_repo.get_data_stamp(scope, rules_version_id)
        key = ":".join((
            self._calculator.policy.policy_version, scope.key,
            str(rules_version_id) if rules_version_id is not None else "none", stamp,
        ))
        cached = await self._cache.read_player(key, player_id)
        if cached is not None:
            logger.info("[GetPlayerLeadsUseCase] Cache hit scope=%s rules=%s", scope.key, rules_version_id)
            return cached

        token = await self._cache.acquire_lock(key)
        started = time.perf_counter()
        snapshot = await self._compute(scope, rules_version_id)
        logger.info(
            "[GetPlayerLeadsUseCase] Cache miss scope=%s rules=%s computed in %.2fs (%d players with leads)",
            scope.key, rules_version_id, time.perf_counter() - started, len(snapshot.leads_by_player),
        )
        if token is not None:
            try:
                await self._cache.save_snapshot(key, snapshot)
            finally:
                await self._cache.release_lock(key, token)
        return snapshot.for_player(player_id)

    async def _compute(self, scope: AwardPeriodScope, rules_version_id: int | None) -> PlayerLeadsSnapshot:
        samples = await self._leads_repo.get_competition_samples(scope, rules_version_id)
        scope_positions = await self._leads_repo.get_scope_positions(scope)
        return self._calculator.calculate(
            scope_key=scope.key,
            scope_kind=scope.kind,
            samples=samples,
            scope_positions=scope_positions,
            rules_version_id=rules_version_id,
            sfa_available=rules_version_id is not None,
        )

    def _empty(
        self, player_id: int, scope_key: str | None, scope_label: str | None, *,
        supported: bool, rules_version_id: int | None,
    ) -> GetPlayerLeadsResult:
        return GetPlayerLeadsResult(
            player_id=player_id, scope_key=scope_key, scope_label=scope_label, supported=supported,
            policy_version=self._calculator.policy.policy_version, rules_version_id=rules_version_id, items=(),
        )
