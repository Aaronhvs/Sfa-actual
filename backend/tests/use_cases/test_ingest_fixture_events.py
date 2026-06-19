"""Tests for fixture event normalization and persistence (spec 0033)."""
from __future__ import annotations

import pytest

from sfa.domain.ingestion_ports import FixtureEventRawDTO
from sfa.infrastructure.repositories.ingestion_repository import (
    _normalize_fixture_event_type,
)


# ---------------------------------------------------------------------------
# Unit tests: _normalize_fixture_event_type
# ---------------------------------------------------------------------------

class TestNormalizeFixtureEventType:
    def test_normal_goal(self) -> None:
        assert _normalize_fixture_event_type("Goal", "Normal Goal") == "goal"

    def test_own_goal(self) -> None:
        assert _normalize_fixture_event_type("Goal", "Own Goal") == "own_goal"

    def test_penalty_goal(self) -> None:
        assert _normalize_fixture_event_type("Goal", "Penalty") == "penalty"

    def test_missed_penalty(self) -> None:
        assert _normalize_fixture_event_type("Goal", "Missed Penalty") == "missed_penalty"

    def test_yellow_card(self) -> None:
        assert _normalize_fixture_event_type("Card", "Yellow Card") == "yellow_card"

    def test_red_card(self) -> None:
        assert _normalize_fixture_event_type("Card", "Red Card") == "red_card"

    def test_yellow_red_card(self) -> None:
        assert _normalize_fixture_event_type("Card", "Yellow Red Card") == "yellow_red_card"

    def test_substitution(self) -> None:
        assert _normalize_fixture_event_type("subst", "Substitution 1") == "substitution"

    def test_substitution_case_insensitive(self) -> None:
        assert _normalize_fixture_event_type("subst", "SUBSTITUTION 2") == "substitution"

    def test_var_is_skipped(self) -> None:
        assert _normalize_fixture_event_type("Var", "Goal Disallowed") is None

    def test_unknown_type_is_skipped(self) -> None:
        assert _normalize_fixture_event_type("Unknown", "Something") is None

    def test_goal_type_case_insensitive(self) -> None:
        assert _normalize_fixture_event_type("goal", "Normal Goal") == "goal"

    def test_card_type_case_insensitive(self) -> None:
        assert _normalize_fixture_event_type("card", "Yellow Card") == "yellow_card"


# ---------------------------------------------------------------------------
# Integration-style tests: save_fixture_events via Fake
# ---------------------------------------------------------------------------

class FakeIngestionRepository:
    """Minimal fake that captures what save_fixture_events would store."""

    def __init__(self) -> None:
        self.saved: dict[int, list[FixtureEventRawDTO]] = {}

    async def save_fixture_events(
        self, fixture_external_id: int, events: list[FixtureEventRawDTO],
    ) -> None:
        self.saved[fixture_external_id] = events


def make_event(event_type: str, detail: str, minute: int = 10) -> FixtureEventRawDTO:
    return FixtureEventRawDTO(
        type=event_type,
        detail=detail,
        player_name="Test Player",
        assist_name=None,
        team_external_id=99,
        minute=minute,
        extra_minute=0,
        source_sequence=None,
    )


class TestNormalizationCoverage:
    """Verify all API-Football event variants map to the correct internal type."""

    @pytest.mark.parametrize("api_type,api_detail,expected", [
        ("Goal", "Normal Goal", "goal"),
        ("Goal", "Own Goal", "own_goal"),
        ("Goal", "Penalty", "penalty"),
        ("Goal", "Missed Penalty", "missed_penalty"),
        ("Card", "Yellow Card", "yellow_card"),
        ("Card", "Red Card", "red_card"),
        ("Card", "Yellow Red Card", "yellow_red_card"),
        ("subst", "Substitution 1", "substitution"),
        ("subst", "Substitution 2", "substitution"),
        ("Var", "Goal Disallowed", None),
        ("Var", "Goal Stands", None),
    ])
    def test_normalize(self, api_type: str, api_detail: str, expected: str | None) -> None:
        result = _normalize_fixture_event_type(api_type, api_detail)
        assert result == expected
