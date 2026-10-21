from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict

from sfa.domain.player_positions.ports import (
    DurableLineupCapture,
    DurablePositionEvidence,
    PlayerPositionEvidenceRepository,
    RecordPositionEvidenceResult,
)
from sfa.domain.player_positions.services import LineupPositionInterpreter
from sfa.domain.player_positions.value_objects import LineupSlot, StartingLineup


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _players(lineup: dict, starting: bool) -> list[dict]:
    """Accept the raw provider schema or our explicitly identified DTO archive."""
    key = "startXI" if starting else "substitutes"
    entries = lineup.get(key, lineup.get("start_xi", []) if starting else [])
    if not isinstance(entries, list):
        return [{}]
    return [entry.get("player") if isinstance(entry.get("player"), dict) else {}
            if "player" in entry else entry for entry in entries if isinstance(entry, dict)]


def _id(player: dict) -> int | None:
    value = player.get("id", player.get("external_id"))
    return value if type(value) is int and value > 0 else None


class RecordPositionEvidenceUseCase:
    """Preserve source assertions; capture never accepts a habitual position."""

    def __init__(self, repository: PlayerPositionEvidenceRepository) -> None:
        self._repository = repository

    async def execute(
        self, fixture_external_id: int, payload_json: str, source_ref: str, received_at: str,
    ) -> RecordPositionEvidenceResult:
        context = await self._repository.get_fixture_context(fixture_external_id)
        if context is None:
            return RecordPositionEvidenceResult(fixture_external_id, 0, 0, "fixture_not_ingested")
        envelope = json.loads(payload_json)
        if isinstance(envelope, dict):
            parameters = envelope.get("parameters") or {}
            fixture = envelope.get("fixture") or {}
            identities = [parameters.get("fixture"), fixture.get("external_id", fixture.get("id"))]
            if any(str(identity) != str(fixture_external_id) for identity in identities if identity is not None):
                return RecordPositionEvidenceResult(fixture_external_id, 0, 0, "fixture_identity_mismatch")
        if isinstance(envelope, dict) and envelope.get("errors"):
            return RecordPositionEvidenceResult(fixture_external_id, 0, 0, "provider_error")
        lineups = envelope.get("response", envelope.get("lineups", [])) if isinstance(envelope, dict) else envelope
        if not isinstance(lineups, list):
            raise ValueError("Lineup response must be an array")
        if any(not isinstance(item, dict) or not isinstance(item.get("team"), dict) for item in lineups):
            raise ValueError("Lineup missing team identity")
        team_counts = Counter(item["team"].get("id", item["team"].get("external_id")) for item in lineups)
        starters = Counter(_id(p) for item in lineups for p in _players(item, True) if _id(p))
        player_ids = await self._repository.get_player_ids(tuple(sorted({
            _id(p) for item in lineups for starting in (True, False)
            for p in _players(item, starting) if _id(p)
        })))
        teams = dict(context.teams)
        captures = []
        unresolved = set()
        unresolved_starters = set()
        valid_teams = set()
        starting_fingerprints = {}
        for item in lineups:
            team_external_id = item["team"].get("id", item["team"].get("external_id"))
            if team_external_id not in teams:
                # Do not attach an unrelated team's payload to a fixture FK.
                continue
            players = _players(item, True)
            slots = tuple(LineupSlot(_id(p), p.get("grid"), p.get("pos", p.get("position"))) for p in players)
            interpreted = LineupPositionInterpreter().interpret(StartingLineup(
                fixture_external_id, team_external_id, context.season, context.competition_id,
                context.played_at, item.get("formation"), slots, tuple(teams),
            ))
            reason = interpreted.reason
            if team_counts[team_external_id] != 1:
                reason = "duplicate_team_payload"
            elif any(starters[_id(p)] != 1 for p in players if _id(p)):
                reason = "duplicate_or_cross_team_starter"
            identities_valid = (len(players) == 11 and all(_id(p) for p in players)
                                and len({_id(p) for p in players}) == 11)
            identities_valid = identities_valid and team_counts[team_external_id] == 1
            identities_valid = identities_valid and not any(starters[_id(p)] != 1 for p in players if _id(p))
            if identities_valid:
                valid_teams.add(team_external_id)
                starting_fingerprints[str(team_external_id)] = _hash(sorted(_id(p) for p in players))
            status = "interpreted" if reason is None else "uninterpreted" if identities_valid else "invalid"
            observations = {ob.external_id: ob for ob in interpreted.observations} if reason is None else {}
            semantic = {
                "fixture": fixture_external_id, "team": team_external_id,
                "formation": item.get("formation"),
                "starters": sorted(((s.external_id, s.grid, s.coarse_position) for s in slots), key=_json)
                if all(s.external_id for s in slots) else [],
            }
            evidence = []
            for starting in (True, False):
                for player in _players(item, starting):
                    external_id = _id(player)
                    if external_id not in player_ids:
                        unresolved.add(external_id)
                        if starting:
                            unresolved_starters.add(external_id)
                        continue
                    ob = observations.get(external_id) if starting else None
                    kind = "starting_slot" if ob else "starting_participation" if starting else "bench_membership"
                    details = {
                        "external_player_id": external_id, "grid": player.get("grid"),
                        "source_position": player.get("pos", player.get("position")),
                        "valid_start_identity": bool(identities_valid and starting),
                        "habitual_role_accepted": False, "issue": reason,
                        "observation": asdict(ob) if ob else None,
                    }
                    # Enum candidates need a stable JSON representation, never set ordering.
                    if ob:
                        details["observation"]["candidates"] = sorted(c.value for c in ob.candidates)
                    semantic_key = {"lineup": semantic, "player": external_id, "kind": kind, "details": details}
                    evidence.append(DurablePositionEvidence(
                        player_ids[external_id], kind, _hash(semantic_key), ob.sfa_position if ob else None,
                        ob.role.value if ob else None, ob.side.value if ob else None, _json(details),
                    ))
            captures.append(DurableLineupCapture(
                teams[team_external_id], _json(item), _hash(item), status, reason, tuple(evidence),
            ))
        coverage = {
            "fixture_external_id": fixture_external_id, "expected_team_ids": sorted(teams),
            "valid_starting_identity_teams": sorted(valid_teams),
            "both_starting_elevens": valid_teams == set(teams),
            "unresolved_player_ids": sorted(x for x in unresolved if x is not None),
            "unresolved_starting_player_ids": sorted(x for x in unresolved_starters if x is not None),
            "unresolved_missing_identity": None in unresolved,
            "unresolved_starting_identity": None in unresolved_starters,
            "starting_identity_fingerprints": starting_fingerprints,
            "calendar_reconciled": False, "habitual_role_coverage": "unknown",
            "status": "partial",  # A fixture response cannot prove season/calendar completeness.
            "source_hash": hashlib.sha256(payload_json.encode()).hexdigest(),
        }
        return await self._repository.record_lineups(context, tuple(captures), source_ref, received_at, _json(coverage))
