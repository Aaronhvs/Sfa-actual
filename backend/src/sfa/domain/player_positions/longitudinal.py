from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from sfa.domain.player_positions.value_objects import (
    LongitudinalPolicy,
    LongitudinalPositionPreview,
    LongitudinalPositionProfile,
    PlayerStartEvidence,
    PositionChangeProposal,
    PositionFrequency,
    PositionProfileContext,
    RoleSideFrequency,
    RoleSideProfile,
    Side,
    TacticalRole,
)

POLICY = LongitudinalPolicy()


def _date(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Profile dates must include a timezone")
    return result.astimezone(timezone.utc)


def _semantic(entry: PlayerStartEvidence) -> tuple | None:
    o = entry.observation
    return (o.role, o.side, tuple(sorted(o.candidates)), o.sfa_position) if o else None


def _canonical(entries: tuple[PlayerStartEvidence, ...], context: PositionProfileContext) -> tuple:
    grouped = defaultdict(list)
    for entry in entries:
        if entry.context != context:
            raise ValueError("Cannot mix player/team/season/competition/kind contexts")
        o = entry.observation
        if o and (o.external_id, o.fixture_id, o.team_id, o.season, o.competition_id) != (
                context.external_id, entry.fixture_id, context.team_id, context.season, context.competition_id):
            raise ValueError("Observation identity does not match start evidence")
        if o and _date(o.played_at) != _date(entry.played_at):
            raise ValueError("Observation date does not match start evidence")
        grouped[entry.fixture_id].append(entry)
    result = []
    for identity, versions in grouped.items():
        dates = {_date(v.played_at) for v in versions}
        if len(dates) != 1:
            raise ValueError("Conflicting dates for one fixture")
        assertions = {_semantic(v) for v in versions if v.observation is not None}
        conflict = len(assertions) > 1 or any(v.issue == "contradictory_evidence" for v in versions)
        ordered = sorted(versions, key=lambda v: (v.observation is None, v.source_ref or "", repr(v)))
        chosen = ordered[0]
        if conflict:
            chosen = replace(chosen, observation=None, issue="contradictory_evidence")
        result.append((replace(chosen, played_at=next(iter(dates)).isoformat()), tuple(versions)))
    return tuple(sorted(result, key=lambda item: (_date(item[0].played_at), item[0].fixture_id)))


def _frequencies(counts: Counter, denominator: int) -> tuple[PositionFrequency, ...]:
    return tuple(PositionFrequency(value, count, count / denominator)
                 for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _dominant(counts: Counter, n: int) -> str | None:
    if n < POLICY.min_observations or not counts:
        return None
    value, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return value if value != "UNKNOWN" and POLICY.primary_denominator * count >= POLICY.primary_numerator * n else None


def _side_primary(counts: Counter, total: int) -> tuple[str | None, str]:
    known = total - counts["UNKNOWN"]
    if (known < POLICY.min_observations
            or POLICY.coverage_denominator * known < POLICY.coverage_numerator * total):
        return None, "insufficient_side_support"
    side = _dominant(Counter({key: value for key, value in counts.items() if key != "UNKNOWN"}), known)
    return side, "predominant_side" if side else "no_dominant_side"


def position_label(position: str | None, role: TacticalRole, side: Side, side_reason: str) -> str:
    role_names = {"GK": "Portero", "CB": "Defensa central", "FB": "Lateral", "WB": "Carrilero",
                  "DM": "Mediocentro defensivo", "CM": "Centrocampista central", "AM": "Mediapunta",
                  "W": "Extremo", "WM": "Medio de banda", "CF": "Delantero centro", "SS": "Segundo delantero"}
    generic = {"GK": "Portero", "DC": "Defensa central", "LAT": "Lateral", "MC": "Centrocampista",
               "MCO": "Mediapunta", "EXT": "Extremo", "DEL": "Delantero centro"}
    name = role_names.get(role.value, generic.get(position, "Posición indeterminada"))
    if role in {TacticalRole.CB, TacticalRole.FB, TacticalRole.WB, TacticalRole.W}:
        if side in {Side.LEFT, Side.RIGHT}:
            return name + (" izquierdo" if side == Side.LEFT else " derecho")
        if side_reason == "no_dominant_side":
            return name + " · sin lado predominante"
    elif side in {Side.LEFT, Side.RIGHT}:
        return name + (" · izquierda" if side == Side.LEFT else " · derecha")
    return name


def _profile(context: PositionProfileContext, canonical: tuple, as_of: datetime, window: str,
             complete: bool) -> LongitudinalPositionProfile:
    available = [item for item in canonical if _date(item[0].played_at) <= as_of]
    if window == "recent":
        available = [item for item in available
                     if _date(item[0].played_at) >= as_of - timedelta(days=POLICY.max_age_days)][-POLICY.recent_starts:]
    starts = [item[0] for item in available]
    valid = [s.observation for s in starts if s.observation is not None]
    n = len(valid)
    positions = Counter(o.sfa_position or "UNKNOWN" for o in valid)
    roles = Counter(o.role.value for o in valid)
    pairs = Counter((o.role, o.side) for o in valid)
    primary = _dominant(positions, n)
    role = TacticalRole(_dominant(roles, n) or "UNKNOWN")
    position_dist = _frequencies(positions, n)
    role_dist = _frequencies(roles, n)
    pair_dist = tuple(RoleSideFrequency(r, side, count, count / n)
                      for (r, side), count in sorted(pairs.items(), key=lambda item: (-item[1], item[0])))
    sides = []
    for role_value in sorted(r for r in roles if r != "UNKNOWN"):
        counts = Counter(o.side.value for o in valid if o.role.value == role_value)
        total = sum(counts.values())
        known = total - counts["UNKNOWN"]
        side, reason = _side_primary(counts, total)
        sides.append(RoleSideProfile(TacticalRole(role_value), total, known, known / total,
                                     Side(side or "UNKNOWN"), reason, _frequencies(counts, total)))
    main_side = next((s for s in sides if s.role == role), None)
    side = main_side.predominant_side if main_side else Side.UNKNOWN
    side_reason = main_side.reason if main_side else "no_dominant_role"
    coverage = n / len(starts) if complete and starts else None
    reasons = []
    if n < POLICY.min_observations:
        reasons.append("insufficient_unique_fixtures")
    if primary is None:
        reasons.append("no_dominant_position")
    if not complete:
        reasons.append("unknown_start_coverage")
    elif not starts:
        reasons.append("no_known_starts")
    elif POLICY.coverage_denominator * n < POLICY.coverage_numerator * len(starts):
        reasons.append("insufficient_start_coverage")
    conflicts = tuple(s.fixture_id for s in starts if s.issue == "contradictory_evidence")
    if conflicts:
        reasons.append("contradictory_evidence")
    dates = [_date(s.played_at) for s in starts if s.observation]
    latest = max(dates) if dates else None
    freshness = ("missing" if latest is None else
                 "stale" if as_of - latest > timedelta(days=POLICY.max_age_days) else "within_window")
    if freshness == "stale":
        reasons.append("stale_evidence")
    refs = sorted({v.source_ref for _, versions in available for v in versions if v.source_ref})
    versions = sorted({(v.observation.template_version, v.observation.orientation_version,
                        v.observation.projection_version)
                       for _, items in available for v in items if v.observation})
    def secondary(item: PositionFrequency) -> bool:
        return (item.value != "UNKNOWN" and item.count >= POLICY.secondary_min_observations
                and POLICY.secondary_denominator * item.count >= POLICY.secondary_numerator * n)
    return LongitudinalPositionProfile(
        context=context, as_of=as_of.isoformat(), window=window,
        window_basis="known_starts" if complete else "observed_starts",
        window_start=starts[0].played_at if starts else None, selected_starts=len(starts), observations=n,
        excluded_starts=len(starts) - n, start_coverage=coverage, inventory_complete=complete,
        primary_position=primary, primary_role=role, primary_side=side, side_reason=side_reason,
        label=position_label(primary, role, side, side_reason),
        secondary_positions=tuple(f for f in position_dist if f.value != primary and secondary(f)),
        secondary_roles=tuple(f for f in role_dist if f.value != role.value and secondary(f)),
        secondary_pairs=tuple(f for f in pair_dist if f.role != TacticalRole.UNKNOWN
                              and f.count >= POLICY.secondary_min_observations
                              and POLICY.secondary_denominator * f.count >= POLICY.secondary_numerator * n
                              and (f.role, f.side) != (role, side)),
        position_distribution=position_dist, role_distribution=role_dist, role_side_distribution=pair_dist,
        sides_by_role=tuple(sides), conflicting_fixture_ids=conflicts,
        excluded_reasons=tuple(sorted(Counter(s.issue or "missing_observation" for s in starts
                                              if s.observation is None).items())),
        fixture_ids=tuple(s.fixture_id for s in starts), source_refs=tuple(refs), evidence_versions=tuple(versions),
        latest_observation_at=latest.isoformat() if latest else None, freshness=freshness,
        meets_evidence_gates=not reasons, reasons=tuple(reasons),
    )


def _proposal(canonical: tuple, as_of: datetime, dimension: str,
              role_context: TacticalRole | None = None) -> PositionChangeProposal:
    entries = [item[0] for item in canonical if _date(item[0].played_at) <= as_of]
    if role_context is not None:
        entries = [e for e in entries if e.observation and e.observation.role == role_context]
    incumbent = candidate = None
    confirmations = []
    state = "insufficient_observations"
    latest_id = None
    for i, entry in enumerate(entries):
        latest_id = entry.fixture_id
        cutoff = _date(entry.played_at) - timedelta(days=POLICY.max_age_days)
        prior = [e for e in entries[:i + 1] if _date(e.played_at) >= cutoff]

        def counts_for(window: list) -> tuple[Counter, int]:
            observed = [e.observation for e in window if e.observation is not None]
            values = [(o.sfa_position or "UNKNOWN") if dimension == "position" else o.role.value
                      if dimension == "role" else o.side.value for o in observed]
            return Counter(values), len(observed)

        if incumbent is None:
            counts, n = counts_for(prior[-POLICY.recent_starts:])
            incumbent = _side_primary(counts, n)[0] if dimension == "side" else _dominant(counts, n)
            if incumbent:
                state = "stable_observed"
            continue
        counts, n = counts_for(prior[-POLICY.change_buffer_starts:])
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        challenger, support = ranked[0] if ranked else (None, 0)
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        new_counts, _ = counts_for([entry])
        new_value = next(iter(new_counts), "UNKNOWN")
        qualifies = (new_value != "UNKNOWN" and n >= POLICY.change_min_observations
                     and challenger not in {None, "UNKNOWN", incumbent}
                     and POLICY.change_denominator * support >= POLICY.change_numerator * n
                     and POLICY.change_margin_denominator * (support - runner_up) >= POLICY.change_margin_numerator * n)
        if qualifies:
            confirmations = ((confirmations + [entry.fixture_id])[-POLICY.confirmations:]
                             if candidate == challenger else [entry.fixture_id])
            candidate = challenger
            state = "change_proposed" if len(confirmations) == POLICY.confirmations else "switch_pending"
        else:
            candidate, confirmations, state = None, [], "stable_observed"
    relevant_dates = [_date(e.played_at) for e in entries if e.observation and (
        e.observation.sfa_position is not None if dimension == "position" else
        e.observation.role != TacticalRole.UNKNOWN if dimension == "role" else
        e.observation.side != Side.UNKNOWN)]
    last_at = max(relevant_dates) if relevant_dates else None
    if last_at is not None and as_of - last_at > timedelta(days=POLICY.max_age_days):
        candidate, confirmations, state = None, [], "stale_evidence"
    return PositionChangeProposal(dimension, incumbent, candidate, state, tuple(confirmations), latest_id, role_context)


@dataclass(frozen=True)
class PlayerPositionTimeline:
    context: PositionProfileContext
    entries: tuple[PlayerStartEvidence, ...] = ()
    superseded: tuple[PlayerStartEvidence, ...] = ()

    def update(self, entry: PlayerStartEvidence, *, replace_fixture: bool = False) -> PlayerPositionTimeline:
        _canonical((entry,), self.context)
        if entry in self.entries and not replace_fixture:
            return self
        old = (tuple(e for e in self.entries if e.fixture_id == entry.fixture_id and e != entry)
               if replace_fixture else ())
        retained = tuple(e for e in self.entries if e not in old)
        return replace(self, entries=retained if entry in retained else retained + (entry,),
                       superseded=self.superseded + old)

    def preview(self, *, as_of: str, complete_start_inventory: bool = False) -> LongitudinalPositionPreview:
        cutoff = _date(as_of)
        canonical = _canonical(self.entries, self.context)
        observed_roles = sorted({e.observation.role for e, _ in canonical if e.observation
                                 and e.observation.role != TacticalRole.UNKNOWN and _date(e.played_at) <= cutoff})
        proposals = (_proposal(canonical, cutoff, "position"), _proposal(canonical, cutoff, "role"))
        proposals += tuple(_proposal(canonical, cutoff, "side", role) for role in observed_roles)
        return LongitudinalPositionPreview(
            _profile(self.context, canonical, cutoff, "season", complete_start_inventory),
            _profile(self.context, canonical, cutoff, "recent", complete_start_inventory), proposals,
        )
