from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.trophy_results import FINAL_STATUSES, AuthoritativeFixtureResultDTO


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class TitleCorrectionSnapshot:
    document: str

    @property
    def fingerprint(self) -> str:
        return fingerprint(json.loads(self.document))


@dataclass(frozen=True)
class TitleCorrectionPlan:
    evidence: str
    source_hash: str
    before: TitleCorrectionSnapshot
    policy_version: str = "intercontinental-title-v1"


def validate_evidence(document: str) -> dict:
    """Bounded, reviewed 2025 correction. An incomplete source is not a zero."""
    data = json.loads(document)
    for capture in data.values():
        if capture["http_status"] != 200 or capture["payload"].get("errors"):
            raise ValueError("Incomplete provider evidence")
    supercup = data["supercup-final"]["payload"]["response"]
    inter = data["intercontinental-fixtures"]["payload"]["response"]
    targets = [(supercup, 1377400, 531, {85, 47}), (inter, 1491683, 1168, {85, 127})]
    for rows, external_id, league, teams in targets:
        matches = [row for row in rows if row["fixture"]["id"] == external_id]
        if len(matches) != 1:
            raise ValueError("Missing unique final")
        row = matches[0]
        if (row["league"]["id"] != league or row["league"]["season"] != 2025
                or row["league"]["round"].lower() != "final"
                or {row["teams"][side]["id"] for side in ("home", "away")} != teams):
            raise ValueError("Final context changed")
        penalty = row["score"]["penalty"]
        result = AuthoritativeFixtureResultDTO(
            external_id, row["teams"]["home"]["id"], row["teams"]["away"]["id"],
            row["fixture"]["status"]["short"], row["goals"]["home"], row["goals"]["away"],
            penalty["home"], penalty["away"], verified=True,
        )
        winner, _ = result.winner()
        if winner != 85:
            raise ValueError("Final result is missing or conflicts with reviewed champion")
        for side in ("home", "away"):
            if row["teams"][side].get("winner") is not (row["teams"][side]["id"] == winner):
                raise ValueError("Provider winner flag conflicts with score")
    fixtures = data["ligue1-fixtures"]["payload"]["response"]
    regular = [f for f in fixtures if f["league"]["round"].startswith("Regular Season - ")]
    if (len({f["fixture"]["id"] for f in regular}) != 306
            or any(f["fixture"]["status"]["short"] not in FINAL_STATUSES
                   or f["league"]["id"] != 61 or f["league"]["season"] != 2025 for f in regular)):
        raise ValueError("League calendar is incomplete")
    missing = [f for f in regular if f["fixture"]["id"] == 1388000]
    if len(missing) != 1 or missing[0]["fixture"]["status"]["short"] != "AWD":
        raise ValueError("Administrative match must be verified separately")
    standings = data["ligue1-standings"]["payload"]["response"][0]["league"]
    rows = standings["standings"][0]
    if (standings["id"] != 61 or standings["season"] != 2025 or len(rows) != 18
            or rows[0]["rank"] != 1 or rows[0]["team"]["id"] != 85
            or any(row["all"]["played"] != (33 if row["team"]["id"] in {
                missing[0]["teams"]["home"]["id"], missing[0]["teams"]["away"]["id"],
            } else 34) for row in rows)):
        raise ValueError("Final league standings are incomplete")
    players = data["intercontinental-players"]["payload"]["response"]
    if {team["team"]["id"] for team in players} != {85, 127}:
        raise ValueError("Participation teams conflict")
    for team in players:
        seen = set()
        minutes = []
        for player in team["players"]:
            pid = player["player"]["id"]
            if pid in seen:
                raise ValueError("Duplicate participation")
            seen.add(pid)
            minute = player["statistics"][0]["games"]["minutes"] or 0
            if not 0 <= minute <= 120:
                raise ValueError("Invalid participation minutes")
            minutes.append(minute)
        if max(minutes, default=0) != 120 or not 1320 <= sum(minutes) <= 1335:
            raise ValueError("Incomplete extra-time participation")
    return data


@runtime_checkable
class TitleCorrectionRepositoryPort(Protocol):
    async def lock(self) -> None: ...
    async def snapshot(self, evidence: str) -> TitleCorrectionSnapshot: ...
    async def allow_publication(self, allowed: bool) -> None: ...
    async def import_evidence(self, evidence: str) -> tuple[int, int, int]: ...
    async def verify(self, before: TitleCorrectionSnapshot, evidence: str) -> TitleCorrectionSnapshot: ...
    async def restore(self, before: TitleCorrectionSnapshot, after: TitleCorrectionSnapshot, evidence: str) -> None: ...


class InferTitleChampionsPort(Protocol):
    async def execute(self, season: str, rules_version_id: int, competition_id: int | None = None): ...


class InferTitleKnockoutPort(Protocol):
    async def execute(self, competition_id: int, season: str, rules_version_id: int): ...


class CalculateTitleBonusesPort(Protocol):
    async def execute(self, season: str, competition_id: int, rules_version_id: int): ...


class RefreshTitleHonorsPort(Protocol):
    async def execute(self, scope_key: str, rules_version_id: int): ...
