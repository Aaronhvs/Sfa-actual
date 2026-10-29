from __future__ import annotations

import json

import pytest

from sfa.domain.title_correction import validate_evidence
from sfa.domain.trophy_results import AuthoritativeFixtureResultDTO, title_policy
from tests.title_correction_fakes import evidence


@pytest.mark.parametrize("status,goals,penalties,verified,expected", [
    ("PEN", (2, 2), (4, 3), True, (99, 57)),
    ("PEN", (1, 1), (2, 1), True, (99, 57)),
    ("PEN", (0, 0), (3, 5), True, (57, 99)),
    ("PEN", (1, 1), (None, None), True, (None, None)),
    ("PEN", (1, 1), (3, None), True, (None, None)),
    ("PEN", (1, 1), (3, 3), True, (None, None)),
    ("PEN", (2, 1), (4, 3), True, (None, None)),
    ("PEN", (1, 1), (-1, 0), True, (None, None)),
    ("PEN", (1, 1), (4, 3), False, (None, None)),
    ("FT", (1, 2), (None, None), True, (57, 99)),
    ("AET", (3, 2), (None, None), True, (99, 57)),
    ("NS", (1, 0), (None, None), True, (None, None)),
    ("FT", (None, None), (None, None), True, (None, None)),
])
def test_complete_result_is_independent_of_shooter_events(status, goals, penalties, verified, expected):
    result = AuthoritativeFixtureResultDTO(1, 99, 57, status, *goals, *penalties, verified=verified)
    assert result.winner() == expected


def test_intercontinental_is_distinct_from_world_cups():
    assert title_policy("FIFA Intercontinental Cup", "winner") == (4000, .5, "intercontinental-title-v1")
    assert title_policy("FIFA Intercontinental Cup", "runner_up")[0] == 0
    assert title_policy("World Cup", "winner") is None
    assert title_policy("FIFA Club World Cup", "winner") is None


def test_complete_offline_evidence_is_accepted():
    assert validate_evidence(evidence())


@pytest.mark.parametrize("change", ["penalty", "winner", "season", "pending", "standings", "minutes", "duplicate"])
def test_inconsistent_evidence_cannot_be_published(change):
    data = json.loads(evidence())
    final = data["supercup-final"]["payload"]["response"][0]
    if change == "penalty":
        final["score"]["penalty"]["home"] = None
    elif change == "winner":
        final["teams"]["home"]["winner"] = False
    elif change == "season":
        final["league"]["season"] = 2026
    elif change == "pending":
        data["ligue1-fixtures"]["payload"]["response"][0]["fixture"]["status"]["short"] = "NS"
    elif change == "standings":
        table = data["ligue1-standings"]["payload"]["response"][0]["league"]["standings"][0]
        table[0]["all"]["played"] = 33
    elif change == "minutes":
        player = data["intercontinental-players"]["payload"]["response"][0]["players"][0]
        player["statistics"][0]["games"]["minutes"] = 90
    else:
        data["ligue1-fixtures"]["payload"]["response"].append(
            data["ligue1-fixtures"]["payload"]["response"].pop(0))
        data["ligue1-fixtures"]["payload"]["response"][0]["fixture"]["id"] = 1388000
    with pytest.raises(ValueError):
        validate_evidence(json.dumps(data))
