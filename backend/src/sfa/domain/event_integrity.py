from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, replace

from sfa.domain.ingestion_ports import FixtureEventRawDTO
from sfa.domain.scoring.services import (
    ScoreTimeline,
    ShootoutDecider,
    is_missed_penalty_event,
    is_shootout_attempt_event,
)

PARSER_VERSION = "event-integrity-v2"
ACTION_TYPES = frozenset(
    {
        "GOAL",
        "GOAL_PENALTY",
        "ASSIST",
        "CORNER_ASSIST",
        "GOAL_SHOOTOUT",
        "GOAL_SHOOTOUT_DECISIVE",
        "MISSED_SHOOTOUT",
        "MISSED_SHOOTOUT_DECISIVE",
    }
)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class Appearance:
    player_id: int
    external_id: int
    team_id: int
    team_external_id: int
    goals: int
    assists: int
    minutes: int


@dataclass(frozen=True)
class Action:
    player_id: int
    team_id: int
    minute: int
    event_type: str
    score_before: str | None
    score_diff: int | None
    is_away: bool
    source_sequence: int


@dataclass(frozen=True)
class StoredAction:
    event_id: int
    player_id: int
    team_id: int | None
    minute: int
    event_type: str
    score_before: str | None
    score_diff: int | None
    is_away: bool | None


@dataclass(frozen=True)
class FixtureSnapshot:
    fixture_id: int
    external_id: int
    competition_id: int
    season: str
    home_external_id: int
    away_external_id: int
    home_goals: int
    away_goals: int
    appearances: tuple[Appearance, ...]
    actions: tuple[StoredAction, ...]
    fingerprint: str
    image_json: str = "{}"
    missing_stats_player_ids: tuple[int, ...] = ()
    stats_actions: tuple[StoredAction, ...] = ()
    home_team_id: int | None = None
    away_team_id: int | None = None
    status: str = "FT"


@dataclass(frozen=True)
class ActionRevision:
    before: StoredAction | None
    after: Action | None


@dataclass(frozen=True)
class AppearanceRevision:
    before: Appearance
    after: Appearance


@dataclass(frozen=True)
class IntegrityPlan:
    fixture_id: int
    external_id: int
    fingerprint: str
    source_hash: str
    changes: tuple[ActionRevision, ...]
    pending: tuple[str, ...]
    parser_version: str = PARSER_VERSION
    appearance_changes: tuple[AppearanceRevision, ...] = ()
    warnings: tuple[str, ...] = ()
    fixture_goals: tuple[int, int] | None = None


def normalize_context_plan(snapshot: FixtureSnapshot) -> IntegrityPlan:
    """Reconcile retained side flags and algebraic score difference against immutable fixture teams."""
    teams = {a.team_id: a.team_external_id for a in snapshot.appearances}
    if snapshot.home_team_id is not None:
        teams[snapshot.home_team_id] = snapshot.home_external_id
    if snapshot.away_team_id is not None:
        teams[snapshot.away_team_id] = snapshot.away_external_id
    changes = []
    warnings = []
    for old in (*snapshot.actions, *snapshot.stats_actions):
        external_id = teams.get(old.team_id)
        if external_id not in {snapshot.home_external_id, snapshot.away_external_id}:
            warnings.append(f"retained_event_team_unresolved:{old.event_id}")
            continue
        is_away = external_id == snapshot.away_external_id
        difference = old.score_diff
        if old.score_before:
            parts = old.score_before.split(":")
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                home, away = map(int, parts)
                difference = away - home if is_away else home - away
        if old.is_away is not is_away or old.score_diff != difference:
            changes.append(
                ActionRevision(
                    old,
                    Action(
                        old.player_id,
                        old.team_id,
                        old.minute,
                        old.event_type,
                        old.score_before,
                        difference,
                        is_away,
                        -1,
                    ),
                )
            )
    return IntegrityPlan(
        snapshot.fixture_id,
        snapshot.external_id,
        snapshot.fingerprint,
        digest(("retained_context", snapshot.fingerprint)),
        tuple(changes),
        (),
        warnings=tuple(warnings),
    )


def parse_source(external_id: int, payload: dict) -> tuple[FixtureEventRawDTO, ...]:
    if payload.get("errors") or str(payload.get("parameters", {}).get("fixture")) != str(external_id):
        raise ValueError("Provider errors or mismatched fixture identity")
    rows = payload.get("response")
    if not isinstance(rows, list) or payload.get("results") != len(rows):
        raise ValueError("Incomplete provider envelope")
    result = []
    for sequence, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("Malformed source event")
        try:
            minute = row["time"]["elapsed"]
            extra = row["time"].get("extra") or 0
            team = row["team"]["id"]
            if type(minute) is not int or type(extra) is not int or type(team) is not int:
                raise ValueError("Invalid event time or team")
            result.append(
                FixtureEventRawDTO(
                    type=row["type"],
                    detail=row["detail"],
                    player_name=row["player"].get("name") or "",
                    assist_name=row["assist"].get("name"),
                    team_external_id=team,
                    minute=minute,
                    extra_minute=extra,
                    source_sequence=sequence,
                    player_external_id=row["player"].get("id"),
                    assist_external_id=row["assist"].get("id"),
                )
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("Malformed source event") from exc
    return tuple(result)


def _role(kind: str) -> str:
    if "SHOOTOUT" in kind:
        return "shootout"
    return "assist" if kind in {"ASSIST", "CORNER_ASSIST"} else "goal"


def _fresh_appearances(snapshot: FixtureSnapshot, events: tuple[FixtureEventRawDTO, ...], payload: dict | None):
    unresolved_roles = set()
    for event in events:
        if event.type != "Goal" or event.detail not in {"Normal Goal", "Penalty"} or is_shootout_attempt_event(event):
            continue
        if type(event.player_external_id) is not int or event.player_external_id <= 0:
            unresolved_roles.add((event.team_external_id, "goal"))
        if event.assist_name and (type(event.assist_external_id) is not int or event.assist_external_id <= 0):
            unresolved_roles.add((event.team_external_id, "assist"))
    goals = Counter(
        e.player_external_id
        for e in events
        if e.type == "Goal" and e.detail in {"Normal Goal", "Penalty"} and not is_shootout_attempt_event(e)
    )
    assists = Counter(
        e.assist_external_id
        for e in events
        if e.type == "Goal" and e.detail in {"Normal Goal", "Penalty"} and not is_shootout_attempt_event(e)
    )
    fresh = {}
    source_warnings = []
    if payload is not None:
        if payload.get("errors") or str(payload.get("parameters", {}).get("fixture")) != str(snapshot.external_id):
            raise ValueError("Invalid player-statistics source")
        if not isinstance(payload.get("response"), list):
            raise ValueError("Incomplete player-statistics response")
        if payload.get("results", len(payload["response"])) != len(payload["response"]):
            raise ValueError("Incomplete player-statistics envelope")
        for team in payload["response"]:
            team_id = team["team"]["id"]
            if team_id not in {snapshot.home_external_id, snapshot.away_external_id}:
                raise ValueError("Player statistics contain a foreign team")
            for row in team.get("players", []):
                actor_id = row["player"]["id"]
                if type(actor_id) is not int or actor_id <= 0:
                    continue
                if actor_id in fresh:
                    fresh[actor_id] = (None, {})
                    source_warnings.append(f"ambiguous_player_source:{actor_id}")
                    continue
                statistics = row.get("statistics") or []
                if statistics:
                    fresh[actor_id] = (team_id, statistics[0])
    revised, changes, protected, warnings = [], [], set(), source_warnings
    for old in snapshot.appearances:
        actor = old
        entry = fresh.get(old.external_id)
        evidence = entry[1] if entry and entry[0] == old.team_external_id else {}
        evidence_goals = evidence.get("goals") or {}
        for field, role, count in [
            ("goals", "goal", goals[old.external_id]),
            ("assists", "assist", assists[old.external_id]),
        ]:
            key = "total" if field == "goals" else "assists"
            if (
                key in evidence_goals
                and (evidence_goals[key] or 0) == count
                and (old.team_external_id, role) not in unresolved_roles
            ):
                actor = replace(actor, **{field: count})
            elif getattr(old, field) != count or (key in evidence_goals and (evidence_goals[key] or 0) != count):
                protected.add((old.player_id, role))
                warnings.append(f"provider_{role}_counts_conflict:{old.player_id}")
        fresh_minutes = (evidence.get("games") or {}).get("minutes") or 0
        if old.minutes < 1 and type(fresh_minutes) is int and fresh_minutes > 0:
            actor = replace(actor, minutes=fresh_minutes)
        if actor != old:
            changes.append(AppearanceRevision(old, actor))
        revised.append(actor)
    return tuple(revised), tuple(changes), protected, warnings


def _verified_extra_time_score(snapshot, events, stats_payload, fixture_payload, final_score):
    """Some provider cup summaries retain the 90-minute score despite a played extra time."""
    if snapshot.status not in {"PEN", "AET"} or not stats_payload or not fixture_payload:
        return False
    if fixture_payload.get("errors") or str(fixture_payload.get("parameters", {}).get("id")) != str(
        snapshot.external_id
    ):
        return False
    rows = fixture_payload.get("response") or []
    if len(rows) != 1:
        return False
    row = rows[0]
    if (
        row["fixture"]["id"] != snapshot.external_id
        or row["fixture"]["status"]["short"] != snapshot.status
        or row["fixture"]["status"].get("elapsed") != 120
        or row["teams"]["home"]["id"] != snapshot.home_external_id
        or row["teams"]["away"]["id"] != snapshot.away_external_id
    ):
        return False
    regulation = row["score"]["fulltime"]
    if (regulation["home"], regulation["away"]) != (snapshot.home_goals, snapshot.away_goals):
        return False
    ordinary = [
        e for e in events if e.type == "Goal" and not is_missed_penalty_event(e) and not is_shootout_attempt_event(e)
    ]
    first = Counter(e.team_external_id for e in ordinary if e.minute <= 90)
    if (first[snapshot.home_external_id], first[snapshot.away_external_id]) != (
        snapshot.home_goals,
        snapshot.away_goals,
    ):
        return False
    if not any(90 < e.minute <= 120 and e.extra_minute == 0 for e in ordinary):
        return False
    if snapshot.status == "PEN" and final_score[0] != final_score[1]:
        return False
    counts = Counter(e.player_external_id for e in ordinary if e.detail != "Own Goal")
    appearances = {}
    for team in stats_payload.get("response", []):
        for player in team.get("players", []):
            actor = player["player"]["id"]
            data = player.get("statistics") or []
            if not data:
                continue
            goals = data[0].get("goals") or {}
            if (goals.get("total") or 0) != counts[actor]:
                return False
            appearances[actor] = team["team"]["id"]
    for event in ordinary:
        actor_team = appearances.get(event.player_external_id)
        if event.detail == "Own Goal":
            if (
                actor_team not in {snapshot.home_external_id, snapshot.away_external_id}
                or actor_team == event.team_external_id
            ):
                return False
        elif actor_team != event.team_external_id:
            return False
    return True


def prepare_plan(
    snapshot: FixtureSnapshot, payload: dict, stats_payload: dict | None = None, fixture_payload: dict | None = None
) -> IntegrityPlan:
    """Generate only identity-proven operations; never manufacture an event from Stats."""
    source_hash = digest({"events": payload, "players": stats_payload, "fixture": fixture_payload})

    def blocked(reason: str) -> IntegrityPlan:
        return IntegrityPlan(
            snapshot.fixture_id, snapshot.external_id, snapshot.fingerprint, source_hash, (), (reason,)
        )

    try:
        events = parse_source(snapshot.external_id, payload)
        timeline = ScoreTimeline.build(snapshot.home_external_id, snapshot.away_external_id, list(events))
    except ValueError as exc:
        return blocked(str(exc))
    if not snapshot.appearances:
        return blocked("missing_player_stats")
    try:
        appearances, appearance_changes, protected_actors, warnings = _fresh_appearances(
            snapshot, events, stats_payload
        )
    except (ValueError, KeyError, TypeError) as exc:
        return blocked(f"invalid_player_source:{exc}")
    actors = {a.external_id: a for a in appearances}
    if len(actors) != len(snapshot.appearances):
        return blocked("ambiguous_provider_identity")
    expected = []
    protected_occurrences = set()
    decisive = ShootoutDecider.decisive_event_ids(snapshot.home_external_id, snapshot.away_external_id, list(events))
    home = away = 0
    for event in events:
        if event.type != "Goal":
            continue
        shootout = is_shootout_attempt_event(event)
        if shootout:
            actor = actors.get(event.player_external_id)
            if actor is None or actor.team_external_id != event.team_external_id or actor.minutes < 1:
                warnings.append(f"unresolved_shootout_actor:{event.source_sequence}")
                protected_occurrences.add(("shootout", 120, event.team_external_id))
                continue
            kind = "MISSED_SHOOTOUT" if is_missed_penalty_event(event) else "GOAL_SHOOTOUT"
            if id(event) in decisive:
                kind += "_DECISIVE"
            expected.append(
                Action(
                    actor.player_id,
                    actor.team_id,
                    120,
                    kind,
                    None,
                    0,
                    actor.team_external_id == snapshot.away_external_id,
                    event.source_sequence,
                )
            )
            continue
        if is_missed_penalty_event(event):
            continue
        if event.detail not in {"Normal Goal", "Penalty", "Own Goal"}:
            return blocked("unrecognized_goal_detail")
        transition = timeline.transition_for(event)
        home = max(home, transition.home_after)
        away = max(away, transition.away_after)
        if event.detail == "Own Goal":
            continue
        for actor_id, event_type in [
            (event.player_external_id, "GOAL_PENALTY" if event.detail == "Penalty" else "GOAL"),
            (event.assist_external_id, "ASSIST"),
        ]:
            if event_type == "ASSIST" and actor_id is None and not event.assist_name:
                continue
            role = _role(event_type)
            minute = max(1, min(120, event.minute + event.extra_minute))
            actor = actors.get(actor_id)
            if actor is None or type(actor_id) is not int or actor_id <= 0:
                warnings.append(f"unresolved_actor_identity:{role}:{event.source_sequence}")
                protected_occurrences.add((role, minute, event.team_external_id))
                continue
            if actor.team_external_id != event.team_external_id or actor.minutes < 1:
                warnings.append(f"actor_team_or_appearance_conflict:{actor.player_id}")
                protected_occurrences.add((role, minute, event.team_external_id))
                protected_actors.add((actor.player_id, role))
                continue
            if (actor.player_id, role) in protected_actors:
                protected_occurrences.add((role, minute, event.team_external_id))
                continue
            is_away = event.team_external_id == snapshot.away_external_id
            difference = (
                transition.away_before - transition.home_before
                if is_away
                else (transition.home_before - transition.away_before)
            )
            expected.append(
                Action(
                    actor.player_id,
                    actor.team_id,
                    max(1, min(120, event.minute + event.extra_minute)),
                    event_type,
                    f"{transition.home_before}:{transition.away_before}",
                    difference,
                    is_away,
                    event.source_sequence,
                )
            )
    fixture_goals = None
    if (home, away) != (snapshot.home_goals, snapshot.away_goals):
        try:
            verified = _verified_extra_time_score(snapshot, events, stats_payload, fixture_payload, (home, away))
        except (KeyError, TypeError, ValueError):
            verified = False
        if not verified:
            return blocked("timeline_final_score_conflict")
        fixture_goals = (home, away)
        warnings.append("provider_summary_excludes_extra_time:normalized_from_verified_events_and_statistics")
    team_map = {a.team_id: a.team_external_id for a in appearances}
    remaining = [
        a
        for a in snapshot.actions
        if (a.player_id, _role(a.event_type)) not in protected_actors
        and (_role(a.event_type), a.minute, team_map.get(a.team_id)) not in protected_occurrences
    ]
    expected = [
        a for a in expected if (_role(a.event_type), a.minute, team_map.get(a.team_id)) not in protected_occurrences
    ]
    changes = []
    unmatched = []

    # An occurrence is tied to its capture in the manifest. Do not treat minute/actor as a stable source ID.
    for action in expected:
        candidates = [
            a
            for a in remaining
            if a.player_id == action.player_id
            and a.team_id == action.team_id
            and a.minute == action.minute
            and _role(a.event_type) == _role(action.event_type)
        ]
        exact = [a for a in candidates if a.score_before == action.score_before]
        if exact:
            candidates = exact
        if len(candidates) > 1:
            return blocked("ambiguous_occurrence_correspondence")
        if not candidates:
            unmatched.append(action)
            continue
        old = candidates[0]
        remaining.remove(old)
        desired_type = old.event_type if old.event_type == "CORNER_ASSIST" else action.event_type
        action = replace(action, event_type=desired_type)
        if (old.event_type, old.score_before, old.score_diff, old.is_away) != (
            action.event_type,
            action.score_before,
            action.score_diff,
            action.is_away,
        ):
            changes.append(ActionRevision(old, action))
    for action in unmatched:
        candidates = [
            a
            for a in remaining
            if a.team_id == action.team_id
            and a.minute == action.minute
            and _role(a.event_type) == _role(action.event_type)
        ]
        if len(candidates) > 1:
            return blocked("ambiguous_actor_correction")
        old = candidates[0] if candidates else None
        if old:
            remaining.remove(old)
        changes.append(ActionRevision(old, action))
    changes.extend(ActionRevision(old, None) for old in remaining)
    for actor in appearances:
        if actor.minutes > 0 and actor.player_id in snapshot.missing_stats_player_ids:
            if actor.team_external_id not in {snapshot.home_external_id, snapshot.away_external_id}:
                return blocked("stats_appearance_team_conflict")
            changes.append(
                ActionRevision(
                    None,
                    Action(
                        actor.player_id,
                        actor.team_id,
                        90,
                        "STATS",
                        None,
                        None,
                        actor.team_external_id == snapshot.away_external_id,
                        -1,
                    ),
                )
            )
    return IntegrityPlan(
        snapshot.fixture_id,
        snapshot.external_id,
        snapshot.fingerprint,
        source_hash,
        tuple(changes),
        (),
        appearance_changes=appearance_changes,
        warnings=tuple(sorted(set(warnings))),
        fixture_goals=fixture_goals,
    )
