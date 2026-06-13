from __future__ import annotations

import pytest

from sfa.application.use_cases.ingest_competition import _validate_appearance_team


def test_accepts_home_team_snapshot() -> None:
    _validate_appearance_team(
        fixture_id=10,
        team_id=1,
        home_team_id=1,
        away_team_id=2,
    )


def test_accepts_away_team_snapshot() -> None:
    _validate_appearance_team(
        fixture_id=10,
        team_id=2,
        home_team_id=1,
        away_team_id=2,
    )


def test_rejects_team_outside_fixture() -> None:
    with pytest.raises(
        ValueError,
        match=r"fixture_id=10 team_id=3",
    ):
        _validate_appearance_team(
            fixture_id=10,
            team_id=3,
            home_team_id=1,
            away_team_id=2,
        )
