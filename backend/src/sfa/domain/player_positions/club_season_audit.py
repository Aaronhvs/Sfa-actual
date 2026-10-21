"""Explicit cross-competition audit view, never an accepted assignment."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta

from sfa.domain.player_positions.longitudinal import (
    POLICY,
    _canonical,
    _date,
    _dominant,
    _frequencies,
    _semantic,
    _side_primary,
    position_label,
)
from sfa.domain.player_positions.value_objects import (
    PlayerStartEvidence,
    PositionFrequency,
    Side,
    TacticalRole,
)


@dataclass(frozen=True)
class ClubSeasonPositionAudit:
    external_id: int
    team_id: int
    season: str
    as_of: str
    window: str
    competition_ids: tuple[int, ...]
    selected_starts: int
    observations: int
    primary_position: str | None
    primary_role: TacticalRole
    primary_side: Side
    label: str
    position_distribution: tuple[PositionFrequency, ...]
    role_distribution: tuple[PositionFrequency, ...]
    secondary_positions: tuple[PositionFrequency, ...]
    fixture_ids: tuple[int, ...]
    conflicting_fixture_ids: tuple[int, ...]
    source_refs: tuple[str, ...]
    reasons: tuple[str, ...]
    inventory_complete: bool = False
    publishable: bool = False


def audit_club_season(entries: tuple[PlayerStartEvidence, ...], *, as_of: str,
                      window: str = "recent") -> ClubSeasonPositionAudit:
    """Retain competition provenance and forbid another club, season or selection.

    Complete inventory is deliberately unknown: a union of captured XI cannot
    prove the total number of starts. No observation receives a fictional context.
    """
    if not entries or window not in {"season", "recent"}:
        raise ValueError("Require evidence and a season/recent window")
    identities = {(e.context.external_id, e.context.team_id, e.context.season, e.context.team_kind)
                  for e in entries}
    if len(identities) != 1 or next(iter(identities))[3] != "club":
        raise ValueError("Cannot mix player, club, season or national-team evidence")
    external_id, team_id, season, _ = next(iter(identities))
    contexts = defaultdict(list)
    for entry in entries:
        contexts[entry.context].append(entry)
    canonical = [item for context, values in contexts.items() for item in _canonical(tuple(values), context)]
    fixtures = defaultdict(list)
    for entry, versions in canonical:
        fixtures[entry.fixture_id].append((entry, versions))
    selected = []
    for fixture, items in fixtures.items():
        # Same fixture cannot acquire extra votes through another competition.
        dates = {_date(e.played_at) for e, _ in items}
        if len(dates) != 1:
            raise ValueError("Conflicting fixture dates")
        date = next(iter(dates))
        if date > _date(as_of):
            continue
        conflict = (len({e.context.competition_id for e, _ in items}) > 1
                    or len({_semantic(e) for e, _ in items if e.observation}) > 1
                    or any(e.issue == "contradictory_evidence" for e, _ in items))
        selected.append((date, fixture, items[0][0], conflict, items))
    selected.sort(key=lambda item: (item[0], item[1]))
    if window == "recent":
        selected = [item for item in selected if item[0] >= _date(as_of) - timedelta(days=POLICY.max_age_days)]
        selected = selected[-POLICY.recent_starts:]
    observations = [e.observation for _, _, e, conflict, _ in selected if e.observation and not conflict]
    n = len(observations)
    positions = Counter(o.sfa_position or "UNKNOWN" for o in observations)
    roles = Counter(o.role.value for o in observations)
    primary = _dominant(positions, n)
    role = TacticalRole(_dominant(roles, n) or "UNKNOWN")
    sides = Counter(o.side.value for o in observations if o.role == role and role != TacticalRole.UNKNOWN)
    side, side_reason = _side_primary(sides, sum(sides.values()))
    side = Side(side or "UNKNOWN")
    conflicts = tuple(f for _, f, _, conflict, _ in selected if conflict)
    reasons = ["unknown_start_coverage"]
    if n < POLICY.min_observations:
        reasons.append("insufficient_unique_fixtures")
    if primary is None:
        reasons.append("no_dominant_position")
    if conflicts:
        reasons.append("contradictory_evidence")
    frequencies = _frequencies(positions, n)
    return ClubSeasonPositionAudit(
        external_id, team_id, season, as_of, window,
        tuple(sorted({e.context.competition_id for _, _, e, _, _ in selected})), len(selected), n,
        primary, role, side, position_label(primary, role, side, side_reason), frequencies,
        _frequencies(roles, n),
        tuple(f for f in frequencies if f.value not in {primary, "UNKNOWN"}
              and f.count >= POLICY.secondary_min_observations
              and POLICY.secondary_denominator * f.count >= POLICY.secondary_numerator * n),
        tuple(f for _, f, _, _, _ in selected), conflicts,
        tuple(sorted({v.source_ref for _, _, _, _, items in selected for _, versions in items
                      for v in versions if v.source_ref})), tuple(reasons),
    )
