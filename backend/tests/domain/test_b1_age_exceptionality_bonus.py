"""Tests for B1AgeExceptionalityBonus value object and _age_at_date helper (spec 0034)."""
from __future__ import annotations

from datetime import date

import pytest

from sfa.domain.scoring.value_objects import B1AgeExceptionalityBonus, ScoringConfig, _age_at_date


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _config(enabled: bool = True) -> ScoringConfig:
    """Return a minimal ScoringConfig with B1 enabled (or disabled)."""
    base = ScoringConfig.default_v2()
    # Rebuild with b1 fields overridden
    d = base.to_dict()
    d["b1_enabled"] = enabled
    d["b1_young_min_age"] = 17
    d["b1_young_max_age"] = 20
    d["b1_veteran_min_age"] = 35
    d["b1_bonus_table"] = {"1": 200, "2": 400, "3": 600}
    return ScoringConfig.from_dict(d)


MATCH_DATE = date(2026, 6, 20)


# ---------------------------------------------------------------------------
# _age_at_date
# ---------------------------------------------------------------------------

class TestAgeAtDate:
    def test_birthday_already_passed_this_year(self) -> None:
        birth = date(2006, 3, 15)   # birthday passed before match
        assert _age_at_date(birth, MATCH_DATE) == 20

    def test_birthday_not_yet_passed_this_year(self) -> None:
        birth = date(2006, 7, 1)    # birthday after match date
        assert _age_at_date(birth, MATCH_DATE) == 19

    def test_exact_birthday_on_match_day(self) -> None:
        birth = date(2006, 6, 20)   # same day
        assert _age_at_date(birth, MATCH_DATE) == 20


# ---------------------------------------------------------------------------
# B1AgeExceptionalityBonus
# ---------------------------------------------------------------------------

class TestB1Disabled:
    def test_returns_zero_when_disabled(self) -> None:
        config = _config(enabled=False)
        birth = date(2009, 1, 1)    # 17 years old — qualifies if enabled
        b1 = B1AgeExceptionalityBonus(
            contributions=1, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 0.0


class TestB1YoungPlayer:
    def test_age_17_qualifies(self) -> None:
        config = _config()
        birth = date(2009, 6, 20)   # exactly 17 on match day
        b1 = B1AgeExceptionalityBonus(
            contributions=1, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 200.0

    def test_age_20_qualifies(self) -> None:
        config = _config()
        birth = date(2006, 3, 1)    # 20 years old at match
        b1 = B1AgeExceptionalityBonus(
            contributions=1, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 200.0

    def test_age_21_does_not_qualify(self) -> None:
        config = _config()
        birth = date(2005, 1, 1)    # 21 years old at match
        b1 = B1AgeExceptionalityBonus(
            contributions=1, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 0.0

    def test_age_34_does_not_qualify(self) -> None:
        config = _config()
        birth = date(1992, 1, 1)    # 34 years old at match
        b1 = B1AgeExceptionalityBonus(
            contributions=1, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 0.0

    def test_1_contribution_yields_200(self) -> None:
        config = _config()
        birth = date(2009, 1, 1)    # 17 years old
        b1 = B1AgeExceptionalityBonus(
            contributions=1, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 200.0

    def test_2_contributions_yield_400(self) -> None:
        config = _config()
        birth = date(2009, 1, 1)
        b1 = B1AgeExceptionalityBonus(
            contributions=2, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 400.0

    def test_3_contributions_yield_600(self) -> None:
        config = _config()
        birth = date(2009, 1, 1)
        b1 = B1AgeExceptionalityBonus(
            contributions=3, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 600.0

    def test_4_contributions_capped_at_600(self) -> None:
        config = _config()
        birth = date(2009, 1, 1)
        b1 = B1AgeExceptionalityBonus(
            contributions=4, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 600.0


class TestB1VeteranPlayer:
    def test_age_35_qualifies(self) -> None:
        config = _config()
        birth = date(1991, 6, 20)   # exactly 35 on match day
        b1 = B1AgeExceptionalityBonus(
            contributions=1, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 200.0

    def test_age_40_qualifies(self) -> None:
        config = _config()
        birth = date(1986, 1, 1)    # 40 years old
        b1 = B1AgeExceptionalityBonus(
            contributions=2, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 400.0


class TestB1EdgeCases:
    def test_none_birth_date_returns_zero(self) -> None:
        config = _config()
        b1 = B1AgeExceptionalityBonus(
            contributions=1, player_birth_date=None, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 0.0

    def test_zero_contributions_returns_zero(self) -> None:
        config = _config()
        birth = date(2009, 1, 1)
        b1 = B1AgeExceptionalityBonus(
            contributions=0, player_birth_date=birth, fixture_date=MATCH_DATE, config=config
        )
        assert b1.value == 0.0
