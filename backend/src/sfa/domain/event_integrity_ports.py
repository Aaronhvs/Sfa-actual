from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.event_integrity import FixtureSnapshot, IntegrityPlan


@runtime_checkable
class SeasonEventIntegrityRepositoryPort(Protocol):
    async def snapshot(self, fixture_id: int) -> FixtureSnapshot: ...
    async def apply(self, plan: IntegrityPlan) -> int: ...
    async def get_context_conflict_fixture_ids(self) -> tuple[int, ...]: ...


@runtime_checkable
class IntegrityJournalPort(Protocol):
    async def write(self, key: str, state: str, payload: str) -> None: ...


@dataclass(frozen=True)
class IntegrityPublicationSnapshot:
    fingerprint: str
    counts: tuple[tuple[str, int], ...]


@runtime_checkable
class SeasonIntegrityPublicationRepositoryPort(Protocol):
    async def lock(self) -> None: ...
    async def validate(self, reverting: bool) -> IntegrityPublicationSnapshot: ...
    async def replace(self, reverting: bool) -> IntegrityPublicationSnapshot: ...
