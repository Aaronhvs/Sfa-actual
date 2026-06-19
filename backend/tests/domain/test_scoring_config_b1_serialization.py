"""Tests for ScoringConfig B1 serialization / backward-compat (spec 0034)."""
from __future__ import annotations

import pytest

from sfa.domain.scoring.value_objects import ScoringConfig


def _b1_config_dict() -> dict:
    d = ScoringConfig.default_v2().to_dict()
    d["b1_enabled"] = True
    d["b1_young_min_age"] = 17
    d["b1_young_max_age"] = 20
    d["b1_veteran_min_age"] = 35
    d["b1_bonus_table"] = {"1": 200, "2": 400, "3": 600}
    d["b1_competition_ids"] = [350]
    return d


class TestScoringConfigB1Serialization:
    def test_roundtrip_to_dict_from_dict(self) -> None:
        config = ScoringConfig.from_dict(_b1_config_dict())
        rebuilt = ScoringConfig.from_dict(config.to_dict())
        assert rebuilt.b1_enabled is True
        assert rebuilt.b1_young_min_age == 17
        assert rebuilt.b1_young_max_age == 20
        assert rebuilt.b1_veteran_min_age == 35
        assert rebuilt.b1_bonus_table == {1: 200, 2: 400, 3: 600}
        assert rebuilt.b1_competition_ids == (350,)

    def test_backward_compat_defaults(self) -> None:
        # Old config dicts (v2) without B1 fields should load with b1_enabled=False
        d = ScoringConfig.default_v2().to_dict()
        d.pop("b1_enabled", None)
        d.pop("b1_bonus_table", None)
        d.pop("b1_competition_ids", None)
        config = ScoringConfig.from_dict(d)
        assert config.b1_enabled is False
        assert config.b1_bonus_table == {1: 200, 2: 400, 3: 600}  # default factory
        assert config.b1_competition_ids == (350,)

    def test_validation_raises_when_enabled_with_empty_table(self) -> None:
        d = _b1_config_dict()
        d["b1_bonus_table"] = {}
        with pytest.raises(ValueError, match="b1_bonus_table cannot be empty"):
            ScoringConfig.from_dict(d)

    def test_validation_raises_when_enabled_with_empty_competition_ids(self) -> None:
        d = _b1_config_dict()
        d["b1_competition_ids"] = []
        with pytest.raises(ValueError, match="b1_competition_ids cannot be empty"):
            ScoringConfig.from_dict(d)

    def test_validation_raises_invalid_age_range(self) -> None:
        d = _b1_config_dict()
        d["b1_young_min_age"] = 25
        d["b1_young_max_age"] = 20   # min > max
        with pytest.raises(ValueError, match="b1_young age range invalid"):
            ScoringConfig.from_dict(d)
