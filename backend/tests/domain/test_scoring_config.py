import pytest

from sfa.domain.scoring.value_objects import ActionType, PositionGroup, ScoringConfig


def _minimal_base_points() -> dict:
    return {
        PositionGroup.FW: {a: 0 for a in ActionType},
        PositionGroup.MF: {a: 0 for a in ActionType},
        PositionGroup.DF: {a: 0 for a in ActionType},
    }


def _valid_config_kwargs() -> dict:
    return {
        "base_points": _minimal_base_points(),
        "m1_clamp": (0.5, 2.0),
        "m1_divisor": 20.0,
        "m4_psxg_multiplier": 0.8,
        "m4_clamp": (1.0, 1.8),
        "mvisit_bonus": 1.3,
        "mvisit_eligible_actions": frozenset({ActionType.GOAL, ActionType.ASSIST}),
        "mrating_thresholds": ((7.0, 0.3), (8.0, 0.5), (8.5, 0.75)),
        "mrating_top_value": 1.0,
        "mrating_none_value": 0.5,
        "combined_clamp": (0.3, 4.0),
    }


class TestScoringConfigInvariants:
    def test_invalid_m1_clamp_min_gt_max_raises(self):
        kwargs = _valid_config_kwargs()
        kwargs["m1_clamp"] = (2.0, 0.5)
        with pytest.raises(ValueError, match="m1_clamp"):
            ScoringConfig(**kwargs)

    def test_invalid_m1_clamp_equal_raises(self):
        kwargs = _valid_config_kwargs()
        kwargs["m1_clamp"] = (1.0, 1.0)
        with pytest.raises(ValueError, match="m1_clamp"):
            ScoringConfig(**kwargs)

    def test_invalid_m1_divisor_zero_raises(self):
        kwargs = _valid_config_kwargs()
        kwargs["m1_divisor"] = 0.0
        with pytest.raises(ValueError, match="m1_divisor"):
            ScoringConfig(**kwargs)

    def test_invalid_m1_divisor_negative_raises(self):
        kwargs = _valid_config_kwargs()
        kwargs["m1_divisor"] = -5.0
        with pytest.raises(ValueError, match="m1_divisor"):
            ScoringConfig(**kwargs)

    def test_invalid_mvisit_bonus_below_one_raises(self):
        kwargs = _valid_config_kwargs()
        kwargs["mvisit_bonus"] = 0.9
        with pytest.raises(ValueError, match="mvisit_bonus"):
            ScoringConfig(**kwargs)

    def test_invalid_combined_clamp_raises(self):
        kwargs = _valid_config_kwargs()
        kwargs["combined_clamp"] = (4.0, 0.3)
        with pytest.raises(ValueError, match="combined_clamp"):
            ScoringConfig(**kwargs)

    def test_empty_base_points_raises(self):
        kwargs = _valid_config_kwargs()
        kwargs["base_points"] = {}
        with pytest.raises(ValueError, match="base_points"):
            ScoringConfig(**kwargs)

    def test_unordered_mrating_thresholds_raises(self):
        kwargs = _valid_config_kwargs()
        kwargs["mrating_thresholds"] = ((8.0, 0.5), (7.0, 0.3))
        with pytest.raises(ValueError, match="mrating_thresholds"):
            ScoringConfig(**kwargs)

    def test_valid_config_constructs_ok(self):
        config = ScoringConfig(**_valid_config_kwargs())
        assert config.m1_divisor == 20.0
        assert config.mvisit_bonus == 1.3


class TestScoringConfigFactories:
    def test_default_produces_same_base_points_as_hardcoded_table(self):
        from sfa.domain.scoring.services import BASE_POINTS_TABLE

        config = ScoringConfig.default()
        for group in BASE_POINTS_TABLE:
            for action in ActionType:
                assert config.base_points[group][action] == BASE_POINTS_TABLE[group][action], (
                    f"Mismatch for {group}/{action}"
                )

    def test_from_dict_roundtrip(self):
        config = ScoringConfig.default()
        serialized = config.to_dict()
        restored = ScoringConfig.from_dict(serialized)

        assert restored.m1_clamp == config.m1_clamp
        assert restored.m1_divisor == config.m1_divisor
        assert restored.mvisit_bonus == config.mvisit_bonus
        assert restored.combined_clamp == config.combined_clamp
        assert restored.mrating_thresholds == config.mrating_thresholds
        for group in config.base_points:
            for action in ActionType:
                assert restored.base_points[group][action] == config.base_points[group][action]

    def test_from_dict_invalid_config_raises_value_error(self):
        with pytest.raises(ValueError):
            ScoringConfig.from_dict({"base_points": {}})

    def test_from_dict_missing_key_raises_value_error(self):
        with pytest.raises(ValueError):
            ScoringConfig.from_dict({})

    def test_to_dict_contains_expected_keys(self):
        d = ScoringConfig.default().to_dict()
        expected_keys = {
            "base_points", "m1_clamp", "m1_divisor", "m4_psxg_multiplier",
            "m4_clamp", "mvisit_bonus", "mvisit_eligible_actions",
            "mrating_thresholds", "mrating_top_value", "mrating_none_value",
            "combined_clamp",
        }
        assert expected_keys.issubset(d.keys())
