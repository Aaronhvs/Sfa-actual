from __future__ import annotations

import json
from types import SimpleNamespace

from sfa.domain.title_correction import TitleCorrectionRepositoryPort, TitleCorrectionSnapshot


def evidence():
    def fixture(external_id, league, home, away, status="PEN", round_name="Final"):
        return {
            "fixture": {"id": external_id, "status": {"short": status}},
            "league": {"id": league, "season": 2025, "round": round_name},
            "teams": {"home": {"id": home, "winner": True}, "away": {"id": away, "winner": False}},
            "goals": {"home": 1, "away": 1}, "score": {"penalty": {"home": 4, "away": 3}},
        }
    regular = [fixture(i, 61, 1, 2, "FT", "Regular Season - 1") for i in range(305)]
    regular.append(fixture(1388000, 61, 71, 96, "AWD", "Regular Season - 34"))
    standings = [{"rank": i + 1, "team": {"id": t}, "all": {"played": 33 if t in {71, 96} else 34}}
                 for i, t in enumerate([85, 71, 96, *range(100, 115)])]
    players = [{"team": {"id": team}, "players": [{"player": {"id": i + 1}, "statistics": [
        {"games": {"minutes": 120}}]} for i in range(11)]} for team in (85, 127)]
    responses = {
        "supercup-final": [fixture(1377400, 531, 85, 47)],
        "intercontinental-fixtures": [fixture(1491683, 1168, 85, 127)],
        "ligue1-fixtures": regular,
        "ligue1-standings": [{"league": {"id": 61, "season": 2025, "standings": [standings]}}],
        "intercontinental-players": players,
    }
    return json.dumps({key: {"http_status": 200, "payload": {"errors": [], "response": value}}
                       for key, value in responses.items()})


class FakeTitleRepository(TitleCorrectionRepositoryPort):
    def __init__(self, calls):
        self.calls, self.value, self.busy = calls, 0, False

    async def lock(self):
        self.calls.append("lock")
        if self.busy:
            raise ValueError("busy")

    async def snapshot(self, evidence):
        return TitleCorrectionSnapshot(json.dumps({"value": self.value}))

    async def allow_publication(self, allowed):
        self.calls.append(("allow", allowed))

    async def import_evidence(self, evidence):
        self.calls.append("import")
        self.value = 1
        return 9, 255, 351

    async def verify(self, before, evidence):
        self.calls.append("verify")
        return await self.snapshot(evidence)

    async def restore(self, before, after, evidence):
        self.calls.append("restore")
        self.value = json.loads(before.document)["value"]


class FakeTitleJournal:
    def __init__(self, calls):
        self.calls, self.entries = calls, []

    async def write(self, key, state, payload):
        self.calls.append(("journal", state))
        self.entries.append((key, state, json.loads(payload)))


class FakeTitleWorkflow:
    def __init__(self, name, calls, failed=False):
        self.name, self.calls, self.failed = name, calls, failed

    async def execute(self, **kwargs):
        self.calls.append((self.name, kwargs))
        return SimpleNamespace(status="failed" if self.failed else "completed")
