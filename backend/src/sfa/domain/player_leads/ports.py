from __future__ import annotations

from typing import Mapping, Protocol, Sequence, runtime_checkable

from sfa.domain.player_leads.models import LeadSample, PlayerLead, PlayerLeadsSnapshot
from sfa.domain.season_scope import AwardPeriodScope


@runtime_checkable
class PlayerLeadsRepositoryProtocol(Protocol):
    async def get_competition_samples(
        self, scope: AwardPeriodScope, rules_version_id: int | None,
    ) -> Sequence[LeadSample]:
        """One sample per (player, season, competition) of the scope, with its context position resolved."""
        ...

    async def get_scope_positions(self, scope: AwardPeriodScope) -> Mapping[int, str | None]:
        """Context position of every player for the scope-wide groups (latest verified club team)."""
        ...

    async def get_data_stamp(self, scope: AwardPeriodScope, rules_version_id: int | None) -> str:
        """Fingerprint that changes whenever scores or finished fixtures of the scope change."""
        ...


@runtime_checkable
class PlayerLeadsCacheProtocol(Protocol):
    async def read_player(self, key: str, player_id: int) -> tuple[PlayerLead, ...] | None:
        """Leads of one player from a cached snapshot; None when no snapshot exists for the key."""
        ...

    async def save_snapshot(self, key: str, snapshot: PlayerLeadsSnapshot) -> None: ...

    async def acquire_lock(self, key: str) -> str | None:
        """Token when the computation lock was taken, None otherwise."""
        ...

    async def release_lock(self, key: str, token: str) -> None: ...


@runtime_checkable
class ScopeRulesVersionResolverProtocol(Protocol):
    """Narrow read port (satisfied by the SFA score repository) for the rules version of a scope."""

    async def resolve_rules_version_id_for_scope(
        self, scope: AwardPeriodScope, preferred_rules_version_id: int | None = None,
    ) -> int: ...
