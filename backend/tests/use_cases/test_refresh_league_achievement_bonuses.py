from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.refresh_league_achievement_bonuses import (
    RefreshLeagueAchievementBonusesUseCase,
)
from sfa.domain.scoring.entities import CompetitionAchievement, ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    PlayerCompetitionAchievementDTO,
)
from tests.use_cases.test_calculate_scores_for_rules_version import FakeScoringRulesVersionRepository

# ─── Fakes ───────────────────────────────────────────────────────────────────


class FakeCompetitionAchievementRepository(CompetitionAchievementRepositoryPort):
    def __init__(
        self,
        pairs: list[tuple[CompetitionAchievement, str]] | None = None,
    ):
        self._pairs = pairs or []
        self.upserted: list[CompetitionAchievement] = []

    async def upsert_achievement(self, achievement: CompetitionAchievement) -> int:
        self.upserted.append(achievement)
        return achievement.id or 1

    async def get_achievements_for_season(self, competition_id, season):
        return []

    async def get_achievements_for_domestic_leagues(
        self, season: str, league_names: list[str]
    ) -> list[tuple[CompetitionAchievement, str]]:
        return [
            (a, name) for a, name in self._pairs
            if a.season == season and name in league_names
        ]

    async def upsert_player_bonus(self, bonus):
        pass

    async def get_team_total_minutes(self, team_id, competition_id, season) -> int:
        return 0

    async def get_player_minutes_in_competition(self, player_id, competition_id, season) -> int:
        return 0

    async def get_players_for_team_season(self, team_id, competition_id, season):
        return []

    async def update_season_score_bonus(
        self, player_id, competition_id, season, rules_version_id, bonus_pts
    ):
        pass

    async def get_player_rank_in_team(
        self, player_id, team_id, competition_id, season, rules_version_id
    ) -> int:
        return 5

    async def get_player_avg_rating(self, player_id, competition_id, season) -> float | None:
        return None

    async def get_competition_ids_for_season(self, season: str) -> list[int]:
        return []

    async def get_player_achievements(
        self, player_id, rules_version_id, season=None
    ) -> list[PlayerCompetitionAchievementDTO]:
        return []


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_version(version_id: int = 4, config: ScoringConfig | None = None) -> ScoringRulesVersion:
    return ScoringRulesVersion(
        id=version_id,
        name="v4-test",
        version="4.0",
        description="",
        is_active=True,
        config=config or ScoringConfig.default_v2(),
        created_at=datetime.now(timezone.utc),
    )


def _make_achievement(
    competition_id: int = 10,
    team_id: int = 1,
    phase: str = "champion",
    bonus_points: int = 7000,
    weight: float = 0.90,
) -> CompetitionAchievement:
    return CompetitionAchievement(
        id=competition_id,
        competition_id=competition_id,
        team_id=team_id,
        season="2024",
        phase=phase,
        bonus_points=bonus_points,
        weight=weight,
        created_at=datetime.now(timezone.utc),
    )


def _make_config_with_domestic_champion(champion_pts: int = 12000) -> ScoringConfig:
    base = ScoringConfig.default_v2()
    bonuses = {k: dict(v) for k, v in base.achievement_phase_bonuses.items()}
    bonuses["domestic_league"] = {"champion": champion_pts, "runner_up": 2500, "top_4": 1000}
    return ScoringConfig(
        base_points=base.base_points,
        m1_clamp=base.m1_clamp,
        m1_divisor=base.m1_divisor,
        m4_psxg_multiplier=base.m4_psxg_multiplier,
        m4_clamp=base.m4_clamp,
        mvisit_bonus=base.mvisit_bonus,
        mvisit_eligible_actions=base.mvisit_eligible_actions,
        mrating_thresholds=base.mrating_thresholds,
        mrating_top_value=base.mrating_top_value,
        mrating_none_value=base.mrating_none_value,
        combined_clamp=base.combined_clamp,
        diminishing_returns=base.diminishing_returns,
        passes_avg_by_position=base.passes_avg_by_position,
        minutes_threshold_stats=base.minutes_threshold_stats,
        minutes_penalty_factor=base.minutes_penalty_factor,
        ranking_min_minutes_global=base.ranking_min_minutes_global,
        ranking_min_minutes_competition=base.ranking_min_minutes_competition,
        m1_strength_divisor=base.m1_strength_divisor,
        league_strength_factors=base.league_strength_factors,
        promoted_champion_strength=base.promoted_champion_strength,
        promoted_runner_up_strength=base.promoted_runner_up_strength,
        promoted_playoff_strength=base.promoted_playoff_strength,
        promoted_default_strength=base.promoted_default_strength,
        cup_lower_div_strengths=base.cup_lower_div_strengths,
        achievement_phase_bonuses=bonuses,
        competition_bonus_weights=base.competition_bonus_weights,
        enable_midfield_control_bonuses=base.enable_midfield_control_bonuses,
        midfield_control_bonus_cap_per_match=base.midfield_control_bonus_cap_per_match,
        enable_performance_based_achievement_bonus=base.enable_performance_based_achievement_bonus,
        m1_stats_weight=base.m1_stats_weight,
        m1_stats_clamp=base.m1_stats_clamp,
        stats_m2_attenuation=base.stats_m2_attenuation,
    )


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestRefreshLeagueAchievementBonusesUseCase:
    @pytest.mark.anyio
    async def test_updates_bonus_points_when_config_changed(self):
        config = _make_config_with_domestic_champion(12000)
        achievement = _make_achievement(bonus_points=7000, weight=0.90)
        repo = FakeCompetitionAchievementRepository(pairs=[(achievement, "La Liga")])
        uc = RefreshLeagueAchievementBonusesUseCase(
            achievement_repo=repo,
            rules_version_repo=FakeScoringRulesVersionRepository(_make_version(4, config)),
        )

        result = await uc.execute(season="2024", rules_version_id=4)

        assert result.status == "completed"
        assert result.achievements_refreshed == 1
        assert result.achievements_skipped == 0
        assert len(repo.upserted) == 1
        assert repo.upserted[0].bonus_points == 12000

    @pytest.mark.anyio
    async def test_skips_unknown_phase(self):
        config = _make_config_with_domestic_champion(12000)
        # "qualify_ko" is not a domestic_league phase
        achievement = _make_achievement(phase="qualify_ko", bonus_points=1000)
        repo = FakeCompetitionAchievementRepository(pairs=[(achievement, "La Liga")])
        uc = RefreshLeagueAchievementBonusesUseCase(
            achievement_repo=repo,
            rules_version_repo=FakeScoringRulesVersionRepository(_make_version(4, config)),
        )

        result = await uc.execute(season="2024", rules_version_id=4)

        assert result.status == "completed"
        assert result.achievements_refreshed == 0
        assert result.achievements_skipped == 1
        assert len(repo.upserted) == 0

    @pytest.mark.anyio
    async def test_no_op_when_no_achievements(self):
        config = _make_config_with_domestic_champion(12000)
        repo = FakeCompetitionAchievementRepository(pairs=[])
        uc = RefreshLeagueAchievementBonusesUseCase(
            achievement_repo=repo,
            rules_version_repo=FakeScoringRulesVersionRepository(_make_version(4, config)),
        )

        result = await uc.execute(season="2024", rules_version_id=4)

        assert result.status == "completed"
        assert result.achievements_refreshed == 0
        assert result.achievements_skipped == 0
        assert len(repo.upserted) == 0

    @pytest.mark.anyio
    async def test_fails_when_rules_version_not_found(self):
        repo = FakeCompetitionAchievementRepository()
        uc = RefreshLeagueAchievementBonusesUseCase(
            achievement_repo=repo,
            rules_version_repo=FakeScoringRulesVersionRepository(None),
        )

        result = await uc.execute(season="2024", rules_version_id=999)

        assert result.status == "failed"
        assert result.error is not None
        assert "999" in result.error
        assert result.achievements_refreshed == 0

    @pytest.mark.anyio
    async def test_updates_weight_from_config(self):
        base = ScoringConfig.default_v2()
        # Modify competition_bonus_weights so La Liga is 0.95
        weights = dict(base.competition_bonus_weights)
        weights["La Liga"] = 0.95
        bonuses = {k: dict(v) for k, v in base.achievement_phase_bonuses.items()}
        bonuses["domestic_league"] = {"champion": 12000, "runner_up": 2500, "top_4": 1000}
        config = ScoringConfig(
            base_points=base.base_points,
            m1_clamp=base.m1_clamp,
            m1_divisor=base.m1_divisor,
            m4_psxg_multiplier=base.m4_psxg_multiplier,
            m4_clamp=base.m4_clamp,
            mvisit_bonus=base.mvisit_bonus,
            mvisit_eligible_actions=base.mvisit_eligible_actions,
            mrating_thresholds=base.mrating_thresholds,
            mrating_top_value=base.mrating_top_value,
            mrating_none_value=base.mrating_none_value,
            combined_clamp=base.combined_clamp,
            diminishing_returns=base.diminishing_returns,
            passes_avg_by_position=base.passes_avg_by_position,
            minutes_threshold_stats=base.minutes_threshold_stats,
            minutes_penalty_factor=base.minutes_penalty_factor,
            ranking_min_minutes_global=base.ranking_min_minutes_global,
            ranking_min_minutes_competition=base.ranking_min_minutes_competition,
            m1_strength_divisor=base.m1_strength_divisor,
            league_strength_factors=base.league_strength_factors,
            promoted_champion_strength=base.promoted_champion_strength,
            promoted_runner_up_strength=base.promoted_runner_up_strength,
            promoted_playoff_strength=base.promoted_playoff_strength,
            promoted_default_strength=base.promoted_default_strength,
            cup_lower_div_strengths=base.cup_lower_div_strengths,
            achievement_phase_bonuses=bonuses,
            competition_bonus_weights=weights,
            enable_midfield_control_bonuses=base.enable_midfield_control_bonuses,
            midfield_control_bonus_cap_per_match=base.midfield_control_bonus_cap_per_match,
            enable_performance_based_achievement_bonus=base.enable_performance_based_achievement_bonus,
            m1_stats_weight=base.m1_stats_weight,
            m1_stats_clamp=base.m1_stats_clamp,
            stats_m2_attenuation=base.stats_m2_attenuation,
        )
        achievement = _make_achievement(bonus_points=7000, weight=0.90)
        repo = FakeCompetitionAchievementRepository(pairs=[(achievement, "La Liga")])
        uc = RefreshLeagueAchievementBonusesUseCase(
            achievement_repo=repo,
            rules_version_repo=FakeScoringRulesVersionRepository(_make_version(4, config)),
        )

        result = await uc.execute(season="2024", rules_version_id=4)

        assert result.status == "completed"
        assert result.achievements_refreshed == 1
        assert repo.upserted[0].bonus_points == 12000
        assert repo.upserted[0].weight == pytest.approx(0.95)
