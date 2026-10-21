from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sfa.domain.player_positions.services import PROJECTION
from sfa.domain.player_positions.value_objects import LongitudinalPositionProfile, Side, TacticalRole

RESOLUTION_POLICY_VERSION = "habitual-position-resolution-v1"
_POSITIONS = frozenset({"GK", "DC", "LAT", "MC", "MCO", "EXT", "DEL"})
_DIMENSIONS = frozenset({"team_id", "competition_id", "season"})


def _date(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Position resolution requires timezone-aware dates")
    return result


@dataclass(frozen=True)
class PositionAssignmentScope:
    team_id: int | None
    competition_id: int | None
    season: str | None
    global_dimensions: frozenset[str]

    def __post_init__(self):
        if self.global_dimensions - _DIMENSIONS:
            raise ValueError("Unknown global context dimension")
        for dimension in _DIMENSIONS:
            value = getattr(self, dimension)
            if (value is None) != (dimension in self.global_dimensions):
                raise ValueError("Every wildcard must declare an explicit global dimension")
            if dimension != "season" and value is not None and (type(value) is not int or value <= 0):
                raise ValueError("Context identities must be positive integer IDs")
            if dimension == "season" and value is not None and not value.strip():
                raise ValueError("Season cannot be empty")


@dataclass(frozen=True)
class PositionResolutionQuery:
    player_id: int
    effective_at: str
    team_id: int | None = None
    competition_id: int | None = None
    season: str | None = None
    purpose: str = "current_habitual"
    external_player_id: int | None = None
    external_team_id: int | None = None
    fixture_id: int | None = None

    def __post_init__(self):
        if type(self.player_id) is not int or self.player_id <= 0:
            raise ValueError("Player ID is required")
        _date(self.effective_at)
        for identity in (self.team_id, self.competition_id, self.external_player_id, self.external_team_id,
                         self.fixture_id):
            if identity is not None and (type(identity) is not int or identity <= 0):
                raise ValueError("Context identities must be positive integer IDs")
        if self.purpose not in {"current_habitual", "historical_habitual"}:
            raise ValueError("Starting slot is not a habitual-role resolution purpose")
        if self.purpose == "historical_habitual" and any(
            getattr(self, dimension) is None for dimension in _DIMENSIONS
        ):
            raise ValueError("Historical resolution requires the fixture's verified context")


@dataclass(frozen=True)
class HabitualPositionAssignment:
    assignment_id: int
    revision_id: str
    player_id: int
    position: str
    scope: PositionAssignmentScope
    effective_from: str
    effective_until: str | None
    status: str
    assertion_kind: str
    evidence_ids: tuple[int, ...]
    source_ref: str
    decision_policy: str
    tactical_role: TacticalRole = TacticalRole.UNKNOWN
    side: Side = Side.UNKNOWN
    secondaries: tuple[str, ...] = ()
    applicable_fixture_ids: frozenset[int] | None = None

    def __post_init__(self):
        if (type(self.assignment_id) is not int or self.assignment_id <= 0
                or type(self.player_id) is not int or self.player_id <= 0):
            raise ValueError("Assignment and player identities must be positive integer IDs")
        if self.applicable_fixture_ids is not None and (
            not isinstance(self.applicable_fixture_ids, frozenset) or not self.applicable_fixture_ids
            or any(type(i) is not int or i <= 0 for i in self.applicable_fixture_ids)
        ):
            raise ValueError("Fixture allowlist must be a nonempty frozenset of positive integer IDs")
        if self.position not in _POSITIONS or any(p not in _POSITIONS for p in self.secondaries):
            raise ValueError("Unsupported SFA position")
        if self.position in self.secondaries or len(set(self.secondaries)) != len(self.secondaries):
            raise ValueError("Secondary positions must be distinct and exclude the primary")
        if self.status not in {"accepted", "draft", "legacy", "superseded"}:
            raise ValueError("Unknown assignment status")
        if self.effective_until is not None and _date(self.effective_until) <= _date(self.effective_from):
            raise ValueError("Assignment interval must have positive duration")
        _date(self.effective_from)
        if self.tactical_role != TacticalRole.UNKNOWN and PROJECTION[self.tactical_role] != self.position:
            raise ValueError("Accepted tactical role and SFA projection must be compatible")
        if self.status == "accepted":
            if self.assertion_kind not in {"habitual_football_role", "curated_fixture_scoring_role"}:
                raise ValueError("A starting-slot observation cannot be an accepted habitual assignment")
            if self.assertion_kind == "curated_fixture_scoring_role" and not self.applicable_fixture_ids:
                raise ValueError("A curated scoring decision requires an explicit fixture allowlist")
            if (not self.evidence_ids or any(type(i) is not int or i <= 0 for i in self.evidence_ids)
                    or len(set(self.evidence_ids)) != len(self.evidence_ids)
                    or not all(s.strip() for s in (self.revision_id, self.source_ref, self.decision_policy))):
                raise ValueError("Accepted assignments require evidence, provenance and decision policy")


@dataclass(frozen=True)
class HabitualPositionCandidate:
    evidence_id: int
    player_id: int
    position: str | None
    assertion_kind: str
    source_ref: str
    scope: PositionAssignmentScope
    effective_from: str
    effective_until: str | None
    identity_verified: bool
    specific_role_verified: bool

    def __post_init__(self):
        if any(type(i) is not int or i <= 0 for i in (self.evidence_id, self.player_id)):
            raise ValueError("Candidate and player identities must be positive integer IDs")
        if type(self.identity_verified) is not bool or type(self.specific_role_verified) is not bool:
            raise ValueError("Source verification flags must be explicit booleans")
        if self.position is not None and self.position not in _POSITIONS:
            raise ValueError("Unsupported candidate position")
        if self.effective_until is not None and _date(self.effective_until) <= _date(self.effective_from):
            raise ValueError("Candidate interval must have positive duration")
        _date(self.effective_from)


@dataclass(frozen=True)
class PositionResolution:
    query: PositionResolutionQuery
    status: str
    position: str | None
    tactical_role: TacticalRole
    side: Side
    secondaries: tuple[str, ...]
    basis: str
    assignment_ids: tuple[int, ...]
    assignment_revision_ids: tuple[str, ...]
    evidence_ids: tuple[int, ...]
    resolution_revision: str
    review_status: str
    pending_reasons: tuple[str, ...]
    conflict_references: tuple[str, ...]
    observed_profile: LongitudinalPositionProfile | None
    legacy_comparison: str | None
    policy_version: str = RESOLUTION_POLICY_VERSION
    publication_enabled: bool = False


def _matches(query, item) -> bool:
    fixture_ids = getattr(item, "applicable_fixture_ids", None)
    return (query.player_id == item.player_id
            and (fixture_ids is None or query.fixture_id in fixture_ids)
            and _date(item.effective_from) <= _date(query.effective_at)
            and (item.effective_until is None or _date(query.effective_at) < _date(item.effective_until))
            and all(d in item.scope.global_dimensions or getattr(item.scope, d) == getattr(query, d)
                    for d in _DIMENSIONS))


class PlayerPositionResolver:
    """Pure temporal resolver. Observed starting slots never become accepted votes.

    No implicit scope precedence is permitted. Incompatible applicable accepted
    claims require review; created_at and database insertion order cannot pick
    one. A coarse incoming candidate cannot overwrite an accepted assignment.
    """

    def resolve(
        self, query: PositionResolutionQuery, assignments: tuple[HabitualPositionAssignment, ...],
        candidates: tuple[HabitualPositionCandidate, ...] = (), *,
        observed_profile: LongitudinalPositionProfile | None = None, legacy_comparison: str | None = None,
    ) -> PositionResolution:
        def distinct(records, identity):
            result = {}
            for record in records:
                key = getattr(record, identity)
                if key in result and result[key] != record:
                    raise ValueError("Contradictory records reuse the same evidence/assignment identity")
                result[key] = record
            return tuple(result.values())

        assignments = distinct(assignments, "assignment_id")
        candidates = distinct(candidates, "evidence_id")
        accepted = tuple(sorted((a for a in assignments if a.status == "accepted" and _matches(query, a)),
                                key=lambda a: (a.revision_id, a.assignment_id)))
        if query.purpose == "current_habitual":
            accepted = tuple(a for a in accepted if a.assertion_kind == "habitual_football_role")
        pending = tuple(sorted((c for c in candidates if _matches(query, c)), key=lambda c: c.evidence_id))
        if observed_profile and (
            observed_profile.context.external_id != query.external_player_id
            or observed_profile.context.team_id != query.external_team_id
            or observed_profile.context.competition_id != query.competition_id
            or observed_profile.context.season != query.season
            or _date(observed_profile.as_of) > _date(query.effective_at)
        ):
            raise ValueError("Observed profile must match the validated provider crosswalk, context and date")
        # Hash every input decision, including candidates, without mutable clock
        # metadata. Sorting and canonical sets make replay order irrelevant.
        manifest = {"query": asdict(query), "assignments": [asdict(a) for a in accepted],
                    "candidates": [asdict(c) for c in pending], "policy": RESOLUTION_POLICY_VERSION,
                    "observed_profile": asdict(observed_profile) if observed_profile else None}
        manifest["query"]["effective_at"] = _date(query.effective_at).astimezone(timezone.utc).isoformat()
        for item in (*manifest["assignments"], *manifest["candidates"]):
            item["effective_from"] = _date(item["effective_from"]).astimezone(timezone.utc).isoformat()
            if item["effective_until"] is not None:
                item["effective_until"] = _date(item["effective_until"]).astimezone(timezone.utc).isoformat()

        def encode(value):
            if isinstance(value, frozenset):
                return sorted(value)
            raise TypeError(f"Unsupported resolution value: {type(value).__name__}")

        revision = hashlib.sha256(json.dumps(manifest, default=encode, sort_keys=True).encode()).hexdigest()
        positions = {a.position for a in accepted}
        roles = {a.tactical_role for a in accepted if a.tactical_role != TacticalRole.UNKNOWN}
        sides = {a.side for a in accepted if a.side != Side.UNKNOWN}
        secondary_sets = {tuple(sorted(a.secondaries)) for a in accepted}
        conflicting = len(positions) > 1 or len(roles) > 1 or len(sides) > 1 or len(secondary_sets) > 1
        specific = tuple(c for c in pending if c.assertion_kind == "habitual_football_role"
                         and c.identity_verified and c.specific_role_verified and c.position in _POSITIONS)
        candidate_conflicts = tuple(c.source_ref for c in specific if accepted and c.position not in positions)
        competing_candidates = not accepted and len({c.position for c in specific}) > 1
        if conflicting:
            status, basis, reasons = "conflicted", "accepted_habitual_role", ("incompatible_accepted_assignments",)
        elif accepted:
            status, basis, reasons = "resolved", ("accepted_curated_scoring_role" if
                any(a.assertion_kind == 'curated_fixture_scoring_role' for a in accepted)
                else "accepted_habitual_role"), ()
        else:
            status = "unknown"
            basis = ("candidate_only" if pending or observed_profile else "legacy_comparison"
                     if legacy_comparison is not None else "no_evidence")
            reasons = ("no_accepted_habitual_assignment_for_context_and_date",)
            if competing_candidates:
                reasons += ("incompatible_specific_habitual_candidates",)
        chosen = accepted[0] if status == "resolved" else None
        # Do not manufacture a joint role+side pair from separate claims.
        detail = max(accepted, key=lambda a: (2 * (a.tactical_role != TacticalRole.UNKNOWN)
                                             + (a.side != Side.UNKNOWN), a.revision_id)) if chosen else None
        return PositionResolution(
            query=query, status=status, position=chosen.position if chosen else None,
            tactical_role=detail.tactical_role if detail else TacticalRole.UNKNOWN,
            side=detail.side if detail else Side.UNKNOWN,
            secondaries=chosen.secondaries if chosen else (), basis=basis,
            assignment_ids=tuple(a.assignment_id for a in accepted),
            assignment_revision_ids=tuple(a.revision_id for a in accepted),
            evidence_ids=tuple(sorted({i for a in accepted for i in a.evidence_ids})),
            resolution_revision=revision,
            review_status="open" if conflicting or candidate_conflicts or competing_candidates else "none",
            pending_reasons=reasons,
            conflict_references=tuple(sorted({c.source_ref for c in specific})) if competing_candidates
            else tuple(sorted(set(candidate_conflicts))) if not conflicting
            else tuple(a.source_ref for a in accepted), observed_profile=observed_profile,
            legacy_comparison=legacy_comparison,
        )
