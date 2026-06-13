from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.calculate_achievement_bonuses import (
    CalculateAchievementBonusesUseCase,
    _compute_rank_factor,
    _compute_rating_factor,
)
from sfa.application.use_cases.calculate_scores_for_rules_version import (
    _MC_BONUS_CONTROL,
    _MC_BONUS_CREATIVE,
    _MC_BONUS_TWO_WAY,
    CalculateScoresForRulesVersionUseCase,
)
from sfa.application.use_cases.register_competition_achievement import (
    RegisterCompetitionAchievementUseCase,
)
from sfa.domain.scoring.entities import (
    CompetitionAchievement,
    PlayerAchievementBonus,
    ScoringRulesVersion,
)
from sfa.domain.scoring.value_objects import ActionType, PositionGroup, ScoringConfig
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    PlayerEventRawContextDTO,
)
from tests.use_cases.test_calculate_scores_for_rules_version import (
    FakePlayerEventScoreRepository,
    FakeScoringRulesVersionRepository,
    _make_rules_version,
)

# ─── Extended Fakes ──────────────────────────────────────────────────────────


class FakePlayerEventScoreRepositoryWithMap(FakePlayerEventScoreRepository):
    def __init__(self, events=None, competition_name_map=None):
        super().__init__(events=events)
        self._competition_name_map = competition_name_map or {}

    async def get_competition_name_map(self) -> dict[int, str]:
        return self._competition_name_map


class FakeCompetitionAchievementRepository(CompetitionAchievementRepositoryPort):
    def __init__(
        self,
        achievements=None,
        team_minutes=0,
        player_minutes=0,
        player_ids=None,
        rank_in_team=5,
        avg_rating=7.5,
    ):
        self._achievements = achievements or []
        self._team_minutes = team_minutes
        self._player_minutes = player_minutes
        self._player_ids = player_ids or []
        self._rank_in_team = rank_in_team
        self._avg_rating = avg_rating
        self.upserted_bonuses: list[PlayerAchievementBonus] = []
        self.upserted_achievements: list[CompetitionAchievement] = []
        self.season_score_updates: list[dict] = []

    async def upsert_achievement(self, achievement) -> int:
        self.upserted_achievements.append(achievement)
        return 1

    async def get_achievements_for_season(self, competition_id, season):
        return [
            achievement for achievement in self._achievements
            if achievement.competition_id == competition_id and achievement.season == season
        ]

    async def upsert_player_bonus(self, bonus):
        self.upserted_bonuses.append(bonus)

    async def get_team_total_minutes(self, team_id, competition_id, season) -> int:
        return self._team_minutes

    async def get_player_minutes_in_competition(self, player_id, competition_id, season) -> int:
        return self._player_minutes

    async def get_players_for_team_season(self, team_id, competition_id, season):
        return self._player_ids

    async def update_season_score_bonus(self, player_id, competition_id, season, rules_version_id, bonus_pts):
        self.season_score_updates.append({"player_id": player_id, "bonus_pts": bonus_pts})

    async def get_player_rank_in_team(self, player_id, team_id, competition_id, season, rules_version_id) -> int:
        return self._rank_in_team

    async def get_player_avg_rating(self, player_id, competition_id, season) -> float | None:
        return self._avg_rating

    async def get_competition_ids_for_season(self, season: str) -> list[int]:
        return list({achievement.competition_id for achievement in self._achievements})

    async def get_achievements_for_domestic_leagues(
        self, season: str, league_names: list[str]
    ) -> list[tuple]:
        return []

    async def get_player_achievements(self, player_id, rules_version_id, season=None):
        return []


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_mc_event(competition_id=1, **overrides):
    defaults = dict(
        event_id=1, player_id=10, fixture_id=100, competition_id=competition_id,
        season="2024", event_type="stats", minute=90, score_diff=0, psxg=None,
        player_team_pos=5, rival_team_pos=8, is_away=False, stage_factor=1.0,
        goals=0, assists=0, shots_on=0, passes_key=3, passes_total=80,
        passes_accuracy=73, dribbles_won=1, duels_won=3,
        tackles_won=2, interceptions=2, blocks=0,
        fouls_drawn=1, fouls_committed=0, cards_yellow=0, cards_red=0,
        penalty_won=0, dribbles_past=0, rating=7.8, player_position="MC",
        minutes=75, player_team_strength=None, rival_team_strength=None,
    )
    defaults.update(overrides)
    return PlayerEventRawContextDTO(**defaults)


def _make_v2_rv(version_id=3):
    return _make_rules_version(version_id=version_id, config=ScoringConfig.default_v2())


def _make_achievement(bonus_points=5000, weight=1.0, team_id=1):
    return CompetitionAchievement(
        id=1, competition_id=1, team_id=team_id, season="2024",
        phase="winner", bonus_points=bonus_points, weight=weight,
        created_at=datetime.now(timezone.utc),
    )


async def _run_scoring(events, rv, competition_name_map=None):
    event_repo = FakePlayerEventScoreRepositoryWithMap(
        events=events, competition_name_map=competition_name_map or {}
    )
    rules_repo = FakeScoringRulesVersionRepository(version=rv)
    use_case = CalculateScoresForRulesVersionUseCase(
        rules_version_repo=rules_repo,
        event_score_repo=event_repo,
    )
    await use_case.execute(rules_version_id=rv.id, season="2024", force_recalculate=True)
    return event_repo.upserted


# ─── Tests Fase 1: nuevos valores de midfield bonuses ────────────────────────


@pytest.mark.anyio
async def test_mc_bonus_control_new_value_140():
    """CONTROL_MIDFIELD_BONUS base is 140."""
    assert _MC_BONUS_CONTROL == 140
    # passes_accuracy=73 = 73 completed / 80 total = 91.25% ≥ 90% → CONTROL earned
    event = _make_mc_event(passes_total=80, passes_accuracy=73, passes_key=0,
                           tackles_won=0, interceptions=0, rating=7.8)
    scores = await _run_scoring([event], _make_v2_rv())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["control_midfield_bonus_earned"] is True
    assert mb["mc_bonus_total_base"] == 140


@pytest.mark.anyio
async def test_mc_bonus_two_way_new_value_90():
    """TWO_WAY_MIDFIELD_BONUS base is 90."""
    assert _MC_BONUS_TWO_WAY == 90
    # passes_accuracy=55 = 55/65 = 84.6% < 90% → no CONTROL; TWO_WAY: defensive=4 ✓
    event = _make_mc_event(passes_total=65, passes_accuracy=55, passes_key=0,
                           tackles_won=2, interceptions=2, rating=7.5)
    scores = await _run_scoring([event], _make_v2_rv())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["two_way_midfield_bonus_earned"] is True
    assert mb["control_midfield_bonus_earned"] is False
    assert mb["mc_bonus_total_base"] == 90


@pytest.mark.anyio
async def test_mc_bonus_creative_new_value_70():
    """CREATIVE_CONTROL_BONUS base is 70."""
    assert _MC_BONUS_CREATIVE == 70
    # passes_accuracy=57 = 57/65 = 87.7% ≥ 85% ✓; 57 ≥ 55 ✓; key=3 ≥ 2 ✓
    # CONTROL: 57 < 65 → NO; TWO_WAY: defensive=0 < 3 → NO
    event = _make_mc_event(passes_total=65, passes_accuracy=57, passes_key=3,
                           tackles_won=0, interceptions=0, rating=7.7)
    scores = await _run_scoring([event], _make_v2_rv())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["creative_control_bonus_earned"] is True
    assert mb["control_midfield_bonus_earned"] is False
    assert mb["mc_bonus_total_base"] == 70


@pytest.mark.anyio
async def test_mc_creative_not_applied_when_accuracy_below_85():
    """CREATIVE requires passes_accuracy >= 85."""
    # passes_accuracy=57 (57/70=81.4% < 85%) → CREATIVE NOT earned
    event = _make_mc_event(passes_total=70, passes_accuracy=57, passes_key=3,
                           tackles_won=0, interceptions=0, rating=7.8)
    scores = await _run_scoring([event], _make_v2_rv())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["creative_control_bonus_earned"] is False


@pytest.mark.anyio
async def test_mc_creative_not_applied_when_rating_below_7_7():
    """CREATIVE requires rating >= 7.7."""
    # passes_accuracy=57 (57/65=87.7% ≥ 85%) but rating=7.6 < 7.7 → NOT earned
    event = _make_mc_event(passes_total=65, passes_accuracy=57, passes_key=3,
                           tackles_won=0, interceptions=0, rating=7.6)
    scores = await _run_scoring([event], _make_v2_rv())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["creative_control_bonus_earned"] is False


@pytest.mark.anyio
async def test_mc_cap_new_value_180():
    """Cap is 180 (140+90+70=300 > 180 → capped to 180)."""
    # passes_accuracy=73 (73/80=91.25% ≥ 90%); all three earned
    event = _make_mc_event(passes_total=80, passes_accuracy=73, passes_key=3,
                           tackles_won=2, interceptions=2, rating=7.8)
    scores = await _run_scoring([event], _make_v2_rv())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["mc_bonus_capped"] is True
    assert mb["mc_bonus_total_base"] == 180


@pytest.mark.anyio
async def test_mc_bonus_includes_competition_weight():
    """competition_weight is applied: mc_bonus_final = base × M2 × Mrating × weight."""
    # Premier League weight in default_v2 = 0.95
    comp_name_map = {1: "Premier League"}
    # CREATIVE only: passes_accuracy=57 (57/65=87.7%≥85%), 57≥55, key=3≥2, rating=7.7≥7.7
    # CONTROL: 57<65 → NO; TWO_WAY: defensive=0<3 → NO
    event = _make_mc_event(competition_id=1, passes_total=65, passes_accuracy=57,
                           passes_key=3, tackles_won=0, interceptions=0, rating=7.7,
                           stage_factor=1.0)
    scores = await _run_scoring([event], _make_v2_rv(), competition_name_map=comp_name_map)
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["competition_weight"] == pytest.approx(0.95)
    # Mrating for 7.7 in v2 thresholds: [7.5, 8.0) → 1.00
    expected = round(70 * 1.0 * 1.0 * 0.95, 2)
    assert mb["mc_bonus_final"] == expected


@pytest.mark.anyio
async def test_mc_bonus_defaults_weight_1_when_competition_unknown():
    """Unknown competition_id defaults competition_weight to 1.0."""
    event = _make_mc_event(competition_id=999, passes_total=80, passes_accuracy=73,
                           passes_key=0, tackles_won=0, interceptions=0, rating=7.8)
    scores = await _run_scoring([event], _make_v2_rv(), competition_name_map={})
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["competition_weight"] == 1.0


# ─── Tests Fase 2: BASE_POINTS_TABLE_V2 ──────────────────────────────────────


def test_base_points_mf_xa_no_assist_95():
    config = ScoringConfig.default_v2()
    assert config.base_points[PositionGroup.MF][ActionType.XA_NO_ASSIST] == 95


def test_base_points_mf_fouls_drawn_25():
    config = ScoringConfig.default_v2()
    assert config.base_points[PositionGroup.MF][ActionType.FOULS_DRAWN] == 25


def test_base_points_mf_duels_won_18():
    config = ScoringConfig.default_v2()
    assert config.base_points[PositionGroup.MF][ActionType.DUELS_WON] == 18


def test_base_points_mf_ballon_dor_midfield_values():
    config = ScoringConfig.default_v2()
    assert config.base_points[PositionGroup.MF][ActionType.PASSES_COMPLETED] == 7
    assert config.passes_avg_by_position[PositionGroup.MF] == 42
    assert config.base_points[PositionGroup.MF][ActionType.TACKLES] == 95
    assert config.base_points[PositionGroup.MF][ActionType.INTERCEPTIONS] == 130


# ─── Tests: achievement phase bonuses ────────────────────────────────────────


def test_achievement_phase_bonuses_domestic_league_exists():
    config = ScoringConfig.default_v2()
    assert config.achievement_phase_bonuses["domestic_league"]["champion"] == 7000


def test_achievement_phase_bonuses_champions_league_winner_5000():
    config = ScoringConfig.default_v2()
    assert config.achievement_phase_bonuses["champions_league"]["winner"] == 5000


def test_achievement_phase_bonuses_runner_up_removed_from_ucl():
    config = ScoringConfig.default_v2()
    assert "runner_up" not in config.achievement_phase_bonuses["champions_league"]


# ─── Tests: performance_factor helpers ───────────────────────────────────────


def test_performance_factor_top3_high_rating():
    assert _compute_rank_factor(2, 0.50) == 1.20
    assert _compute_rating_factor(8.2) == 1.20
    result = max(0.50, min(1.35, 1.20 * 1.20))
    assert result == 1.35


def test_performance_factor_low_participation_override():
    assert _compute_rank_factor(1, 0.15) == 0.50


def test_performance_factor_no_rating():
    assert _compute_rating_factor(None) == 1.00


# ─── Tests: achievement bonus with performance_factor ────────────────────────


@pytest.mark.anyio
async def test_achievement_bonus_uses_performance_factor_when_enabled():
    """With enable_performance_based_achievement_bonus=True applies performance_factor."""
    # player_minutes=2000, team=8000, ratio=0.25
    # rank=3 → rank_factor=1.20; rating=7.8 → rating_factor=1.10
    # performance_factor = min(1.35, 1.20*1.10) = min(1.35, 1.32) = 1.32
    # bonus = 5000 * 1.0 * 0.25 * 1.32 = 1650.0
    config = ScoringConfig.default_v2()
    assert config.enable_performance_based_achievement_bonus is True

    rv = ScoringRulesVersion(
        id=3, name="v2", version="2.0", description="", is_active=True,
        config=config, created_at=datetime.now(timezone.utc),
    )
    achievement = _make_achievement(bonus_points=5000, weight=1.0)
    repo = FakeCompetitionAchievementRepository(
        achievements=[achievement],
        team_minutes=8000,
        player_minutes=2000,
        player_ids=[99],
        rank_in_team=3,
        avg_rating=7.8,
    )
    rules_repo = FakeScoringRulesVersionRepository(version=rv)
    use_case = CalculateAchievementBonusesUseCase(
        achievement_repo=repo, rules_version_repo=rules_repo
    )
    result = await use_case.execute(season="2024", competition_id=1, rules_version_id=3)
    assert result.status == "completed"
    assert len(repo.upserted_bonuses) == 1
    assert repo.upserted_bonuses[0].final_bonus == pytest.approx(1650.0)


@pytest.mark.anyio
async def test_achievement_bonus_retrocompat_when_flag_disabled():
    """With enable_performance_based_achievement_bonus=False uses original formula."""
    import dataclasses
    config_off = dataclasses.replace(
        ScoringConfig.default_v2(), enable_performance_based_achievement_bonus=False
    )
    rv = ScoringRulesVersion(
        id=3, name="v2", version="2.0", description="", is_active=True,
        config=config_off, created_at=datetime.now(timezone.utc),
    )
    achievement = _make_achievement(bonus_points=5000, weight=1.0)
    repo = FakeCompetitionAchievementRepository(
        achievements=[achievement],
        team_minutes=8000,
        player_minutes=2000,
        player_ids=[99],
    )
    rules_repo = FakeScoringRulesVersionRepository(version=rv)
    use_case = CalculateAchievementBonusesUseCase(
        achievement_repo=repo, rules_version_repo=rules_repo
    )
    await use_case.execute(season="2024", competition_id=1, rules_version_id=3)
    # original: 5000 * 1.0 * 0.25 = 1250.0
    assert repo.upserted_bonuses[0].final_bonus == pytest.approx(1250.0)


@pytest.mark.anyio
async def test_register_achievement_uses_competition_name_not_id():
    """register_competition_achievement uses competition_name for weight lookup."""
    config = ScoringConfig.default_v2()
    assert "Champions League" in config.competition_bonus_weights

    rv = ScoringRulesVersion(
        id=3, name="v2", version="2.0", description="", is_active=True,
        config=config, created_at=datetime.now(timezone.utc),
    )
    from tests.use_cases.test_register_competition_achievement import (
        FakeCompetitionAchievementRepository as FakeAchRepo,
    )
    from tests.use_cases.test_register_competition_achievement import FakeScoringRulesVersionRepository as FakeRVRepo
    repo = FakeAchRepo()
    rules_repo = FakeRVRepo(version=rv)
    use_case = RegisterCompetitionAchievementUseCase(
        achievement_repo=repo, rules_version_repo=rules_repo
    )
    result = await use_case.execute(
        competition_id=10, team_id=1, season="2024",
        phase="winner", rules_version_id=3,
        competition_name="Champions League",
    )
    assert result.status == "registered"
    assert repo.achievements[-1].weight == config.competition_bonus_weights["Champions League"]


def test_scoring_config_round_trip_preserves_new_flag():
    config = ScoringConfig.default_v2()
    recovered = ScoringConfig.from_dict(config.to_dict())
    assert recovered.enable_performance_based_achievement_bonus is True
    assert recovered.midfield_control_bonus_cap_per_match == 180


def test_scoring_config_v1_default_false_for_new_flag():
    config_v1 = ScoringConfig.default()
    assert config_v1.enable_performance_based_achievement_bonus is False
    d = config_v1.to_dict()
    del d["enable_performance_based_achievement_bonus"]
    recovered = ScoringConfig.from_dict(d)
    assert recovered.enable_performance_based_achievement_bonus is False
