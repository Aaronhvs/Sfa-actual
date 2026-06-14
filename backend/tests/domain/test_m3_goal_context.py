from __future__ import annotations

from sfa.domain.scoring.value_objects import M3MinuteScore


def test_late_goal_reducing_large_deficit_has_low_impact() -> None:
    assert M3MinuteScore(73, -3, is_penalty=False).value == 0.75


def test_late_goal_reducing_one_goal_deficit_remains_valuable() -> None:
    assert M3MinuteScore(73, -1, is_penalty=False).value == 1.6


def test_late_go_ahead_goal_remains_valuable() -> None:
    assert M3MinuteScore(73, 0, is_penalty=False).value == 1.8
