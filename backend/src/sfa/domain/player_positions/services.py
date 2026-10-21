import re
from collections import Counter, defaultdict
from types import MappingProxyType

from sfa.domain.player_positions.value_objects import (
    LineupInterpretation,
    PositionObservation,
    PositionSupport,
    Quality,
    Side,
    StartingLineup,
    TacticalRole,
)

R = TacticalRole


def _row(*roles: str) -> tuple[frozenset[TacticalRole], ...]:
    return tuple(frozenset(R(role) for role in slot.split("/")) for slot in roles)


B4 = _row("FB", "CB", "CB", "FB")
B3 = _row("CB", "CB", "CB")
B5 = _row("FB/WB", "CB", "CB", "CB", "FB/WB")
TEMPLATES = MappingProxyType({
    "4-3-3": (B4, _row("CM", "CM", "CM"), _row("W", "CF", "W")),
    "4-2-3-1": (B4, _row("DM/CM", "DM/CM"), _row("W/AM", "AM", "W/AM"), _row("CF")),
    "4-4-2": (B4, _row("WM", "CM", "CM", "WM"), _row("CF", "CF")),
    "4-1-4-1": (B4, _row("DM"), _row("WM", "CM", "CM", "WM"), _row("CF")),
    "3-5-2": (B3, _row("WB/WM", "CM", "CM", "CM", "WB/WM"), _row("CF", "CF")),
    "3-4-3": (B3, _row("WB/WM", "CM", "CM", "WB/WM"), _row("W", "CF", "W")),
    "3-4-1-2": (B3, _row("WB/WM", "CM", "CM", "WB/WM"), _row("AM"), _row("CF", "CF")),
    "3-4-2-1": (B3, _row("WB/WM", "CM", "CM", "WB/WM"), _row("AM", "AM"), _row("CF")),
    "5-3-2": (B5, _row("CM", "CM", "CM"), _row("CF", "CF")),
    "4-3-1-2": (B4, _row("CM", "CM", "CM"), _row("AM"), _row("CF", "CF")),
    "4-1-2-1-2": (B4, _row("DM"), _row("CM", "CM"), _row("AM"), _row("CF", "CF")),
    "4-2-2-2": (B4, _row("DM/CM", "DM/CM"), _row("AM/WM", "AM/WM"), _row("CF", "CF")),
})
PROJECTION = MappingProxyType({
    R.GK: "GK", R.CB: "DC", R.FB: "LAT", R.WB: "LAT", R.DM: "MC", R.CM: "MC",
    R.AM: "MCO", R.W: "EXT", R.WM: None, R.CF: "DEL", R.SS: None, R.UNKNOWN: None,
})
COARSE = MappingProxyType({
    R.GK: frozenset("G"), R.CB: frozenset("D"), R.FB: frozenset("D"),
    R.WB: frozenset("DM"), R.DM: frozenset("M"), R.CM: frozenset("M"),
    R.AM: frozenset("MF"), R.W: frozenset("MF"), R.WM: frozenset("M"), R.CF: frozenset("F"),
})


class LineupPositionInterpreter:
    """Interpret starting slots, never names, current positions or match minutes.

    Templates are hypotheses about geometry, not verified player profiles. All
    outputs remain candidates; side is disabled for unrecognized orientation.
    """

    def interpret(self, lineup: StartingLineup) -> LineupInterpretation:
        if lineup.schema != "api-football-grid-v3":
            return LineupInterpretation((), "unknown_schema")
        if lineup.team_id not in lineup.participant_team_ids or len(set(lineup.participant_team_ids)) != 2:
            return LineupInterpretation((), "team_not_in_fixture")
        template = TEMPLATES.get(lineup.formation)
        if template is None:
            return LineupInterpretation((), "unsupported_formation")
        if len(lineup.starters) != 11:
            return LineupInterpretation((), "expected_eleven_starters")
        ids = [slot.external_id for slot in lineup.starters]
        if any(type(value) is not int or value <= 0 for value in ids):
            return LineupInterpretation((), "missing_player_identity")
        if len(set(ids)) != 11:
            return LineupInterpretation((), "duplicate_player_identity")
        rows = (_row("GK"),) + template
        expected = {(row, col): roles for row, slots in enumerate(rows, 1)
                    for col, roles in enumerate(slots, 1)}
        parsed = []
        for slot in lineup.starters:
            if not isinstance(slot.grid, str) or not re.fullmatch(r"[1-9]\d*:[1-9]\d*", slot.grid):
                return LineupInterpretation((), "missing_or_malformed_grid")
            coordinates = tuple(map(int, slot.grid.split(":")))
            parsed.append((slot, coordinates))
        if len({coordinates for _, coordinates in parsed}) != 11:
            return LineupInterpretation((), "duplicate_grid")
        if {coordinates for _, coordinates in parsed} != set(expected):
            return LineupInterpretation((), "grid_formation_mismatch")
        goalkeepers = [coordinates for slot, coordinates in parsed if slot.coarse_position == "G"]
        if goalkeepers != [(1, 1)]:
            return LineupInterpretation((), "invalid_goalkeeper")
        for slot, coordinates in parsed:
            roles = expected[coordinates]
            if slot.coarse_position is not None and not any(slot.coarse_position in COARSE[r] for r in roles):
                return LineupInterpretation((), "coarse_position_inconsistent")
        observations = []
        for slot, (row, col) in sorted(parsed, key=lambda pair: pair[1]):
            candidates = expected[(row, col)]
            role = next(iter(candidates)) if len(candidates) == 1 else R.UNKNOWN
            projections = {PROJECTION[candidate] for candidate in candidates}
            sfa_position = next(iter(projections)) if len(projections) == 1 else None
            side = Side.UNKNOWN
            if lineup.orientation == "column-1-team-left-v1":
                width = len(rows[row - 1])
                side = Side.CENTER if col * 2 == width + 1 else Side.LEFT if col * 2 < width + 1 else Side.RIGHT
            observations.append(PositionObservation(
                external_id=slot.external_id, fixture_id=lineup.fixture_id, team_id=lineup.team_id,
                season=lineup.season, competition_id=lineup.competition_id, played_at=lineup.played_at,
                role=role, side=side, candidates=candidates,
                role_quality=Quality.SPECIFIC if role != R.UNKNOWN else Quality.AMBIGUOUS,
                side_quality=Quality.SPECIFIC if side != Side.UNKNOWN else Quality.MISSING,
                sfa_position=sfa_position, reason="starting_slot" if role != R.UNKNOWN else "ambiguous_starting_slot",
                orientation_version=lineup.orientation,
            ))
        return LineupInterpretation(tuple(observations))


def aggregate_position_support(
    observations: tuple[PositionObservation, ...], *, known_starts: int | None = None,
    complete_start_inventory: bool = False,
) -> PositionSupport:
    """Aggregate one player/team/competition/season/explicit observation period.

    Three fixtures, 2/3 modal support and 60% coverage are pilot policy gates,
    not statistical confidence. Unknown slots stay in all support denominators.
    """
    contexts = {(o.external_id, o.team_id, o.competition_id, o.season) for o in observations}
    if len(contexts) > 1:
        raise ValueError("Cannot aggregate different player/team/competition/season contexts")
    by_fixture = defaultdict(set)
    for observation in observations:
        by_fixture[observation.fixture_id].add(observation)
    conflicts = sum(len(values) > 1 for values in by_fixture.values())
    valid = [next(iter(values)) for values in by_fixture.values() if len(values) == 1]
    n = len(valid)
    role_counts = Counter(o.role.value for o in valid)
    side_counts = Counter(o.side.value for o in valid)
    projection_counts = Counter(o.sfa_position or "UNKNOWN" for o in valid)
    pair_counts = Counter((o.role.value, o.side.value) for o in valid)

    def supported(counts: Counter) -> str | None:
        if n < 3 or not counts:
            return None
        value, support = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        return value if value != "UNKNOWN" and 3 * support >= 2 * n else None

    role = R(supported(role_counts) or "UNKNOWN")
    side = Side(supported(side_counts) or "UNKNOWN")
    projection = supported(projection_counts)
    if side != Side.UNKNOWN:
        compatible_side_support = sum(
            o.side == side and (o.role == role if role != R.UNKNOWN else
                               o.sfa_position == projection if projection is not None else True)
            for o in valid
        )
        if 3 * compatible_side_support < 2 * n:
            side = Side.UNKNOWN
    denominator_known = (complete_start_inventory and type(known_starts) is int
                         and known_starts >= len(by_fixture) and known_starts > 0)
    coverage = n / known_starts if denominator_known else None
    reasons = []
    if n < 3:
        reasons.append("insufficient_unique_fixtures")
    if conflicts:
        reasons.append("contradictory_duplicate_fixture")
    if projection is None:
        reasons.append("insufficient_projection_support")
    if not denominator_known:
        reasons.append("unknown_start_coverage")
    elif 5 * n < 3 * known_starts:
        reasons.append("insufficient_start_coverage")
    return PositionSupport(
        n, conflicts, known_starts if denominator_known else None, coverage, role, side, projection,
        tuple(sorted(role_counts.items())), tuple(sorted(side_counts.items())),
        tuple(sorted(projection_counts.items())),
        tuple((role, side, count) for (role, side), count in sorted(pair_counts.items())),
        not reasons, tuple(reasons),
    )
