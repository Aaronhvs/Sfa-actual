from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.player_positions.publication import (
    PositionCorrectionCapture,
    PositionCorrectionPlan,
    PositionCorrectionRequest,
    PositionPublicationResult,
    SeasonPositionCorrectionPlan,
)
from sfa.domain.player_positions.value_objects import PositionAuditSnapshot


@runtime_checkable
class PositionAuditSnapshotSource(Protocol):
    async def load(self) -> PositionAuditSnapshot: ...


@dataclass(frozen=True)
class LineupEvidenceResponse:
    fixture_id: int | None
    http_status: int
    body: str
    fetched_at: str
    daily_remaining: int | None
    minute_remaining: int | None
    minute_limit: int | None
    transport_error: str | None = None


@runtime_checkable
class LineupEvidenceProvider(Protocol):
    async def status(self) -> LineupEvidenceResponse: ...

    async def fetch_lineups(self, fixture_id: int) -> LineupEvidenceResponse: ...


@runtime_checkable
class LineupEvidenceArchive(Protocol):
    async def acquire(self) -> None: ...

    async def release(self) -> None: ...

    async def load_manifest(self) -> str | None: ...

    async def save_manifest(self, content: str) -> None: ...

    async def load_response(self, fixture_id: int) -> LineupEvidenceResponse | None: ...

    async def save_response(self, response: LineupEvidenceResponse) -> str: ...

    async def save_snapshot(self, content: str) -> None: ...


@dataclass(frozen=True)
class PositionFixtureContext:
    fixture_id: int
    external_id: int
    competition_id: int
    season: str
    played_at: str
    teams: tuple[tuple[int, int], ...]  # external ID, internal ID


@dataclass(frozen=True)
class DurablePositionEvidence:
    player_id: int
    assertion_kind: str
    source_hash: str
    position: str | None
    tactical_role: str | None
    side: str | None
    details_json: str


@dataclass(frozen=True)
class DurableLineupCapture:
    team_id: int
    payload_json: str
    payload_hash: str
    validation_status: str
    validation_reason: str | None
    evidence: tuple[DurablePositionEvidence, ...]


@dataclass(frozen=True)
class RecordPositionEvidenceResult:
    fixture_external_id: int
    snapshots: int
    evidence: int
    status: str


@runtime_checkable
class PlayerPositionEvidenceRepository(Protocol):
    async def get_fixture_context(self, external_id: int) -> PositionFixtureContext | None: ...

    async def get_player_ids(self, external_ids: tuple[int, ...]) -> dict[int, int]: ...

    async def record_lineups(
        self, context: PositionFixtureContext, captures: tuple[DurableLineupCapture, ...],
        source_ref: str, received_at: str, coverage_json: str,
    ) -> RecordPositionEvidenceResult: ...


@runtime_checkable
class PositionEvidenceRecorder(Protocol):
    async def execute(
        self, fixture_external_id: int, payload_json: str, source_ref: str, received_at: str,
    ) -> RecordPositionEvidenceResult: ...


@runtime_checkable
class PositionLineupCollectionState(Protocol):
    async def acquire(self) -> bool: ...

    async def owns_lease(self) -> bool: ...

    async def release(self) -> None: ...

    async def pending(self, season: str, limit: int) -> tuple[int, ...]: ...

    async def checkpoint(self, fixture_id: int | None, state: str, details_json: str) -> None: ...


@runtime_checkable
class PositionCalendarProvider(Protocol):
    async def status(self) -> LineupEvidenceResponse: ...

    async def fetch_calendar(self, league_id: int, season: str) -> LineupEvidenceResponse: ...


@runtime_checkable
class PositionCalendarCoverageState(Protocol):
    async def acquire(self) -> bool: ...

    async def owns_lease(self) -> bool: ...

    async def release(self) -> None: ...

    async def inventory(self, competition_id: int, season: str) -> str: ...

    async def record_calendar(self, scope_key: str, proof_json: str, status: str) -> None: ...


@dataclass(frozen=True)
class PositionIdentityRecord:
    player_id: int
    external_id: int
    stored_position: str
    stored_source: str | None
    legacy_effective_position: str | None = None


@runtime_checkable
class PositionReferenceRepository(Protocol):
    async def identity(self, player_id: int) -> PositionIdentityRecord | None: ...

    async def accept_reference(
        self, player_id: int, position: str, revision_id: str, source_ref: str, statement: str,
        accepted_at: str, actor: str,
        decision_status: str,
    ) -> bool: ...


@runtime_checkable
class PositionCorrectionRepository(Protocol):
    async def capture(self, request: PositionCorrectionRequest, rules_version_id: int) -> PositionCorrectionCapture: ...

    async def published(self, batch_id: str) -> PositionPublicationResult | None: ...

    async def apply(self, plan: PositionCorrectionPlan) -> PositionPublicationResult: ...

    async def revert(self, batch_id: str, actor: str) -> PositionPublicationResult: ...


@runtime_checkable
class PositionCorrectionSimulator(Protocol):
    async def execute(self, request: PositionCorrectionRequest, rules_version_id: int) -> PositionCorrectionPlan: ...


class SeasonPositionImpactSimulator(Protocol):
    def execute(self, snapshot: dict, *, catalog: list[dict], observations: list[dict]): ...


class SeasonPositionCorrectionRepository(Protocol):
    async def published(self, batch_id: str) -> PositionPublicationResult | None: ...

    async def fingerprint(self, scope_json: str, rules_version_id: int) -> str: ...

    async def apply(self, plan: SeasonPositionCorrectionPlan) -> PositionPublicationResult: ...

    async def revert(self, batch_id: str, actor: str) -> PositionPublicationResult: ...
