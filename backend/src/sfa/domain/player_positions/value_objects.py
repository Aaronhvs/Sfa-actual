from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TacticalRole(str, Enum):
    GK = "GK"
    CB = "CB"
    FB = "FB"
    WB = "WB"
    DM = "DM"
    CM = "CM"
    AM = "AM"
    W = "W"
    WM = "WM"
    CF = "CF"
    SS = "SS"
    UNKNOWN = "UNKNOWN"


class Side(str, Enum):
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"
    UNKNOWN = "UNKNOWN"


class Quality(str, Enum):
    SPECIFIC = "specific"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"
    INCONSISTENT = "inconsistent"


@dataclass(frozen=True)
class LineupSlot:
    external_id: int | None
    grid: str | None
    coarse_position: str | None


@dataclass(frozen=True)
class StartingLineup:
    fixture_id: int
    team_id: int
    season: str
    competition_id: int
    played_at: str
    formation: str | None
    starters: tuple[LineupSlot, ...]
    participant_team_ids: tuple[int, int]
    schema: str = "api-football-grid-v3"
    orientation: str = "column-1-team-left-v1"


@dataclass(frozen=True)
class PositionObservation:
    external_id: int
    fixture_id: int
    team_id: int
    season: str
    competition_id: int
    played_at: str
    role: TacticalRole
    side: Side
    candidates: frozenset[TacticalRole]
    role_quality: Quality
    side_quality: Quality
    sfa_position: str | None
    reason: str
    template_version: str = "starting-grid-v1"
    orientation_version: str = "column-1-team-left-v1"
    projection_version: str = "sfa-projection-v1"


@dataclass(frozen=True)
class LineupInterpretation:
    observations: tuple[PositionObservation, ...]
    reason: str | None = None


@dataclass(frozen=True)
class PositionSupport:
    observations: int
    conflicting_fixtures: int
    known_starts: int | None
    coverage: float | None
    role: TacticalRole
    side: Side
    sfa_position: str | None
    role_distribution: tuple[tuple[str, int], ...]
    side_distribution: tuple[tuple[str, int], ...]
    projection_distribution: tuple[tuple[str, int], ...]
    role_side_distribution: tuple[tuple[str, str, int], ...]
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PositionAuditSnapshot:
    """Serialized snapshot kept at the port boundary; decoded by the application."""

    content: str
    sha256: str


@dataclass(frozen=True)
class PositionProfileContext:
    external_id: int
    team_id: int
    season: str
    competition_id: int
    team_kind: str = "unspecified"


@dataclass(frozen=True)
class PlayerStartEvidence:
    context: PositionProfileContext
    fixture_id: int
    played_at: str
    observation: PositionObservation | None = None
    issue: str | None = None
    source_ref: str | None = None


@dataclass(frozen=True)
class LongitudinalPolicy:
    version: str = "longitudinal-profile-v1"
    min_observations: int = 3
    primary_numerator: int = 2
    primary_denominator: int = 3
    secondary_min_observations: int = 2
    secondary_numerator: int = 1
    secondary_denominator: int = 5
    coverage_numerator: int = 3
    coverage_denominator: int = 5
    recent_starts: int = 10
    max_age_days: int = 180
    change_buffer_starts: int = 8
    change_min_observations: int = 6
    change_numerator: int = 3
    change_denominator: int = 4
    change_margin_numerator: int = 1
    change_margin_denominator: int = 5
    confirmations: int = 2


@dataclass(frozen=True)
class PositionFrequency:
    value: str
    count: int
    share: float


@dataclass(frozen=True)
class RoleSideFrequency:
    role: TacticalRole
    side: Side
    count: int
    share: float


@dataclass(frozen=True)
class RoleSideProfile:
    role: TacticalRole
    observations: int
    known_sides: int
    side_coverage: float
    predominant_side: Side
    reason: str
    distribution: tuple[PositionFrequency, ...]


@dataclass(frozen=True)
class PositionChangeProposal:
    dimension: str
    incumbent: str | None
    candidate: str | None
    state: str
    confirmation_fixture_ids: tuple[int, ...]
    evaluated_fixture_id: int | None
    role_context: TacticalRole | None = None


@dataclass(frozen=True)
class LongitudinalPositionProfile:
    context: PositionProfileContext
    as_of: str
    window: str
    window_basis: str
    window_start: str | None
    selected_starts: int
    observations: int
    excluded_starts: int
    start_coverage: float | None
    inventory_complete: bool
    primary_position: str | None
    primary_role: TacticalRole
    primary_side: Side
    side_reason: str
    label: str
    secondary_positions: tuple[PositionFrequency, ...]
    secondary_roles: tuple[PositionFrequency, ...]
    secondary_pairs: tuple[RoleSideFrequency, ...]
    position_distribution: tuple[PositionFrequency, ...]
    role_distribution: tuple[PositionFrequency, ...]
    role_side_distribution: tuple[RoleSideFrequency, ...]
    sides_by_role: tuple[RoleSideProfile, ...]
    conflicting_fixture_ids: tuple[int, ...]
    excluded_reasons: tuple[tuple[str, int], ...]
    fixture_ids: tuple[int, ...]
    source_refs: tuple[str, ...]
    evidence_versions: tuple[tuple[str, str, str], ...]
    latest_observation_at: str | None
    freshness: str
    meets_evidence_gates: bool
    reasons: tuple[str, ...]
    policy_version: str = "longitudinal-profile-v1"
    candidate_only: bool = True
    profile_kind: str = "observed_starting_slots"


@dataclass(frozen=True)
class LongitudinalPositionPreview:
    season: LongitudinalPositionProfile
    recent: LongitudinalPositionProfile
    proposals: tuple[PositionChangeProposal, ...]
    policy: LongitudinalPolicy = LongitudinalPolicy()
