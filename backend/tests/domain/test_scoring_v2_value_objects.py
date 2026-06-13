import pytest

from sfa.domain.scoring.value_objects import (
    ActionType,
    DiminishingReturnsConfig,
    M1RivalDifficulty,
    PositionGroup,
    ScoringConfig,
    TeamStrengthBlend,
    position_to_group,
)
from sfa.infrastructure.models.enums import Position


class TestPositionGroupV2:
    def test_five_groups_exist(self):
        assert PositionGroup.DEL.value == "DEL"
        assert PositionGroup.EXT.value == "EXT"
        assert PositionGroup.MF.value == "MF"
        assert PositionGroup.LAT.value == "LAT"
        assert PositionGroup.DC.value == "DC"

    def test_legacy_groups_still_exist_for_backward_compat(self):
        assert PositionGroup.FW.value == "FW"
        assert PositionGroup.DF.value == "DF"

    def test_position_to_group_all_five_positions(self):
        assert position_to_group(Position.DEL) == PositionGroup.DEL
        assert position_to_group(Position.EXT) == PositionGroup.EXT
        assert position_to_group(Position.MC)  == PositionGroup.MF
        assert position_to_group(Position.LAT) == PositionGroup.LAT
        assert position_to_group(Position.DC)  == PositionGroup.DC

    def test_gk_raises_value_error(self):
        with pytest.raises(ValueError):
            position_to_group(Position.GK)


class TestDiminishingReturnsConfig:
    def test_apply_below_cap_uses_full_base(self):
        cfg = DiminishingReturnsConfig(cap=5, extra_factor=0.25)
        result = DiminishingReturnsConfig.apply(3, 100.0, cfg)
        assert result == pytest.approx(300.0)

    def test_apply_at_cap_uses_full_base(self):
        cfg = DiminishingReturnsConfig(cap=5, extra_factor=0.25)
        result = DiminishingReturnsConfig.apply(5, 100.0, cfg)
        assert result == pytest.approx(500.0)

    def test_apply_above_cap_uses_extra_factor(self):
        cfg = DiminishingReturnsConfig(cap=5, extra_factor=0.25)
        # 5 × 100 + 3 × 100 × 0.25 = 500 + 75 = 575
        result = DiminishingReturnsConfig.apply(8, 100.0, cfg)
        assert result == pytest.approx(575.0)

    def test_apply_zero_count_returns_zero(self):
        cfg = DiminishingReturnsConfig(cap=5, extra_factor=0.25)
        assert DiminishingReturnsConfig.apply(0, 100.0, cfg) == 0.0

    def test_invalid_cap_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="cap"):
            DiminishingReturnsConfig(cap=0, extra_factor=0.25)

    def test_invalid_cap_negative_raises_value_error(self):
        with pytest.raises(ValueError, match="cap"):
            DiminishingReturnsConfig(cap=-1, extra_factor=0.25)

    def test_invalid_extra_factor_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="extra_factor"):
            DiminishingReturnsConfig(cap=5, extra_factor=0.0)

    def test_invalid_extra_factor_one_raises_value_error(self):
        with pytest.raises(ValueError, match="extra_factor"):
            DiminishingReturnsConfig(cap=5, extra_factor=1.0)


class TestTeamStrengthBlend:
    def test_early_matchday_weights_prev_heavily(self):
        blend = TeamStrengthBlend(prev_season_strength=80.0, current_season_strength=20.0, matchday=3)
        # 0.8 × 80 + 0.2 × 20 = 64 + 4 = 68
        assert blend.value == pytest.approx(68.0)

    def test_late_matchday_weights_current_heavily(self):
        blend = TeamStrengthBlend(prev_season_strength=20.0, current_season_strength=80.0, matchday=20)
        # 0.2 × 20 + 0.8 × 80 = 4 + 64 = 68
        assert blend.value == pytest.approx(68.0)

    def test_mid_matchday_6_to_10(self):
        blend = TeamStrengthBlend(prev_season_strength=100.0, current_season_strength=0.0, matchday=8)
        # 0.6 × 100 + 0.4 × 0 = 60
        assert blend.value == pytest.approx(60.0)

    def test_mid_matchday_11_to_15(self):
        blend = TeamStrengthBlend(prev_season_strength=100.0, current_season_strength=0.0, matchday=13)
        # 0.4 × 100 + 0.6 × 0 = 40
        assert blend.value == pytest.approx(40.0)

    def test_no_matchday_uses_50_50(self):
        blend = TeamStrengthBlend(prev_season_strength=60.0, current_season_strength=40.0, matchday=None)
        assert blend.value == pytest.approx(50.0)

    def test_no_prev_uses_current_only(self):
        blend = TeamStrengthBlend(prev_season_strength=None, current_season_strength=70.0, matchday=5)
        assert blend.value == pytest.approx(70.0)

    def test_no_current_uses_prev_only(self):
        blend = TeamStrengthBlend(prev_season_strength=60.0, current_season_strength=None, matchday=5)
        assert blend.value == pytest.approx(60.0)

    def test_both_none_uses_fallback(self):
        blend = TeamStrengthBlend(prev_season_strength=None, current_season_strength=None, fallback_strength=30.0)
        assert blend.value == pytest.approx(30.0)

    def test_result_clamped_to_0_100(self):
        blend = TeamStrengthBlend(prev_season_strength=120.0, current_season_strength=110.0, matchday=20)
        assert blend.value == pytest.approx(100.0)

        blend_low = TeamStrengthBlend(prev_season_strength=-10.0, current_season_strength=-5.0, matchday=20)
        assert blend_low.value == pytest.approx(0.0)


class TestM1RivalDifficultyV2:
    def test_with_strengths_uses_strength_formula(self):
        m1 = M1RivalDifficulty(player_team_strength=40.0, rival_team_strength=80.0)
        # 1.0 + (80 - 40) / 100 = 1.4, clamp [0.5, 2.0] (no config) → 1.4
        assert m1.value == pytest.approx(1.4)

    def test_without_strengths_uses_legacy_formula(self):
        m1 = M1RivalDifficulty(player_team_pos=5, rival_team_pos=15)
        # 1.0 + (5 - 15) / 20 = 0.5 → clamped to 0.5
        assert m1.value == pytest.approx(0.5)

    def test_with_config_uses_config_clamp(self):
        config = ScoringConfig.default_v2()
        m1 = M1RivalDifficulty(
            player_team_strength=10.0, rival_team_strength=90.0, config=config
        )
        # 1.0 + (90 - 10) / 100 = 1.8, clamp [0.6, 1.8] → 1.8
        assert m1.value == pytest.approx(1.8)

    def test_clamp_min_0_6_with_v2_config(self):
        config = ScoringConfig.default_v2()
        m1 = M1RivalDifficulty(
            player_team_strength=90.0, rival_team_strength=10.0, config=config
        )
        # 1.0 + (10 - 90) / 100 = 0.2 → clamped to 0.6
        assert m1.value == pytest.approx(0.6)

    def test_clamp_max_1_8_with_v2_config(self):
        config = ScoringConfig.default_v2()
        m1 = M1RivalDifficulty(
            player_team_strength=0.0, rival_team_strength=100.0, config=config
        )
        # 1.0 + 100/100 = 2.0 → clamped to 1.8
        assert m1.value == pytest.approx(1.8)

    def test_no_data_returns_neutral(self):
        m1 = M1RivalDifficulty()
        assert m1.value == pytest.approx(1.0)


class TestScoringConfigV2:
    def test_default_v2_produces_6_position_groups(self):
        config = ScoringConfig.default_v2()
        assert set(config.base_points.keys()) == {
            PositionGroup.DEL, PositionGroup.EXT, PositionGroup.MCO, PositionGroup.MF,
            PositionGroup.LAT, PositionGroup.DC,
        }

    def test_default_v2_has_diminishing_returns_for_6_actions(self):
        config = ScoringConfig.default_v2()
        expected = {
            ActionType.XG_NO_GOAL, ActionType.XA_NO_ASSIST,
            ActionType.DUELS_WON, ActionType.TACKLES,
            ActionType.INTERCEPTIONS, ActionType.BLOCKS,
        }
        assert set(config.diminishing_returns.keys()) == expected

    def test_default_v2_mvisit_bonus_is_1_15(self):
        config = ScoringConfig.default_v2()
        assert config.mvisit_bonus == pytest.approx(1.15)

    def test_default_v2_m4_clamp_max_is_1_5(self):
        config = ScoringConfig.default_v2()
        assert config.m4_clamp[1] == pytest.approx(1.5)

    def test_default_v2_minutes_threshold_is_15(self):
        config = ScoringConfig.default_v2()
        assert config.minutes_threshold_stats == 15

    def test_from_dict_roundtrip_v2(self):
        config = ScoringConfig.default_v2()
        restored = ScoringConfig.from_dict(config.to_dict())
        assert restored.mvisit_bonus == config.mvisit_bonus
        assert restored.minutes_threshold_stats == config.minutes_threshold_stats
        assert restored.m1_clamp == config.m1_clamp
        assert len(restored.diminishing_returns) == len(config.diminishing_returns)

    def test_v1_config_still_deserializes_with_fw_df_groups(self):
        v1_dict = ScoringConfig.default().to_dict()
        restored = ScoringConfig.from_dict(v1_dict)
        assert PositionGroup.FW in restored.base_points
        assert PositionGroup.DF in restored.base_points

    def test_invalid_minutes_threshold_raises(self):
        with pytest.raises(ValueError):
            ScoringConfig.default_v2().__class__(
                **{**ScoringConfig.default_v2().__dict__, "minutes_threshold_stats": -1}
            )

    def test_invalid_minutes_penalty_factor_raises(self):
        config = ScoringConfig.default_v2()
        d = config.to_dict()
        d["minutes_penalty_factor"] = 0.0
        with pytest.raises(ValueError):
            ScoringConfig.from_dict(d)
