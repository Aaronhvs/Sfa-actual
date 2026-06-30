from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.infer_competition_achievements import (
    InferAllCompetitionAchievementsUseCase,
    InferCompetitionAchievementsUseCase,
)
from sfa.domain.infer_achievements_ports import (
    InferAchievementsRepositoryPort,
    KnockoutFixtureDTO,
)
from sfa.domain.scoring.entities import CompetitionAchievement, ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import CompetitionAchievementRepositoryPort, ScoringRulesVersionRepositoryPort


# ─── Fakes ───────────────────────────────────────────────────────────────────


class FakeInferAchievementsRepository(InferAchievementsRepositoryPort):
    def __init__(
        self,
        fixtures: list[KnockoutFixtureDTO] | None = None,
        goals: dict[int, dict[int, int]] | None = None,
        shootout_goals: dict[int, dict[int, int]] | None = None,
        competition_name: str = "Champions League",
        all_knockout_ids: list[int] | None = None,
    ):
        self._fixtures = fixtures or []
        self._goals = goals or {}
        self._shootout_goals = shootout_goals or {}
        self._competition_name = competition_name
        self._all_knockout_ids = all_knockout_ids or []

    async def get_knockout_stage_fixtures(self, competition_id: int, season: str) -> list[KnockoutFixtureDTO]:
        return self._fixtures

    async def get_goals_for_fixture(self, fixture_id: int) -> dict[int, int]:
        return self._goals.get(fixture_id, {})

    async def get_shootout_goals_for_fixture(self, fixture_id: int) -> dict[int, int]:
        return self._shootout_goals.get(fixture_id, {})

    async def get_competition_name(self, competition_id: int) -> str:
        return self._competition_name

    async def get_all_knockout_competition_ids(self, season: str) -> list[int]:
        return self._all_knockout_ids


class FakeCompetitionAchievementRepository(CompetitionAchievementRepositoryPort):
    def __init__(self):
        self.upserted: list[CompetitionAchievement] = []
        self.deleted: list[tuple[int, str]] = []
        self._next_id = 1

    async def upsert_achievement(self, achievement: CompetitionAchievement) -> int:
        self.upserted.append(achievement)
        aid = self._next_id
        self._next_id += 1
        return aid

    async def delete_achievements_for_competition_season(
        self, competition_id: int, season: str
    ) -> None:
        self.deleted.append((competition_id, season))

    async def get_achievements_for_season(self, competition_id: int, season: str) -> list[CompetitionAchievement]:
        return []

    async def upsert_player_bonus(self, bonus) -> None:
        pass

    async def get_team_total_minutes(self, team_id: int, competition_id: int, season: str) -> int:
        return 0

    async def get_player_minutes_in_competition(self, player_id: int, competition_id: int, season: str) -> int:
        return 0

    async def get_players_for_team_season(self, team_id: int, competition_id: int, season: str) -> list[int]:
        return []

    async def update_season_score_bonus(self, player_id, competition_id, season, rules_version_id, bonus_pts) -> None:
        pass

    async def get_player_rank_in_team(self, player_id, team_id, competition_id, season, rules_version_id) -> int:
        return 1

    async def get_player_avg_rating(self, player_id, competition_id, season) -> float | None:
        return None

    async def get_competition_ids_for_season(self, season: str) -> list[int]:
        return []


class FakeScoringRulesVersionRepository(ScoringRulesVersionRepositoryPort):
    def __init__(self, config: ScoringConfig | None = None):
        self._config = config or ScoringConfig.default_v2()

    async def get_active_version(self) -> ScoringRulesVersion | None:
        return ScoringRulesVersion(
            id=3, name="v2", version="2.0", description=None,
            is_active=True, config=self._config, created_at=datetime.now(timezone.utc),
        )

    async def get_version_by_id(self, version_id: int) -> ScoringRulesVersion | None:
        return ScoringRulesVersion(
            id=version_id, name="v2", version="2.0", description=None,
            is_active=True, config=self._config, created_at=datetime.now(timezone.utc),
        )

    async def list_versions(self) -> list[ScoringRulesVersion]:
        return []

    async def save_version(self, name, version, description, config) -> int:
        return 3

    async def set_active_version(self, version_id: int) -> None:
        pass


def _make_use_case(
    fixtures=None, goals=None, shootout_goals=None,
    competition_name="Champions League", all_knockout_ids=None,
):
    infer_repo = FakeInferAchievementsRepository(
        fixtures=fixtures, goals=goals, shootout_goals=shootout_goals,
        competition_name=competition_name, all_knockout_ids=all_knockout_ids,
    )
    achievement_repo = FakeCompetitionAchievementRepository()
    rules_repo = FakeScoringRulesVersionRepository()
    uc = InferCompetitionAchievementsUseCase(infer_repo, achievement_repo, rules_repo)
    return uc, achievement_repo


# ─── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_domestic_league_skipped_when_no_knockout_fixtures():
    uc, repo = _make_use_case(fixtures=[], competition_name="La Liga")
    result = await uc.execute(competition_id=1, season="2025", rules_version_id=3)
    assert result.skipped is True
    assert result.achievements_upserted == 0
    assert repo.upserted == []


@pytest.mark.anyio
async def test_final_winner_correctly_assigned_from_goals():
    fixtures = [KnockoutFixtureDTO(fixture_id=1, stage="final", home_team_id=10, away_team_id=20)]
    goals = {1: {10: 2, 20: 1}}
    uc, repo = _make_use_case(fixtures=fixtures, goals=goals)
    result = await uc.execute(competition_id=10, season="2025", rules_version_id=3)
    assert result.skipped is False
    phases = {a.phase: a.team_id for a in repo.upserted}
    assert phases["winner"] == 10
    assert phases["runner_up"] == 20


@pytest.mark.anyio
async def test_final_winner_assigned_from_shootout_when_regular_time_tied():
    fixtures = [KnockoutFixtureDTO(fixture_id=1, stage="final", home_team_id=10, away_team_id=20)]
    goals = {1: {10: 1, 20: 1}}
    shootout = {1: {10: 4, 20: 3}}
    uc, repo = _make_use_case(fixtures=fixtures, goals=goals, shootout_goals=shootout)
    result = await uc.execute(competition_id=10, season="2025", rules_version_id=3)
    phases = {a.phase: a.team_id for a in repo.upserted}
    assert phases["winner"] == 10
    assert phases["runner_up"] == 20


@pytest.mark.anyio
async def test_final_winner_skips_winner_runner_up_when_all_tied():
    fixtures = [KnockoutFixtureDTO(fixture_id=1, stage="final", home_team_id=10, away_team_id=20)]
    goals = {1: {10: 1, 20: 1}}
    shootout = {1: {10: 3, 20: 3}}
    uc, repo = _make_use_case(fixtures=fixtures, goals=goals, shootout_goals=shootout)
    result = await uc.execute(competition_id=10, season="2025", rules_version_id=3)
    assert result.skipped is False
    assert {a.phase for a in repo.upserted} == {"semi_final"}
    assert {a.team_id for a in repo.upserted} == {10, 20}


@pytest.mark.anyio
async def test_completed_round_of_32_winner_gets_round_of_16_before_next_fixture_exists():
    fixtures = [KnockoutFixtureDTO(fixture_id=1, stage="round_of_32", home_team_id=10, away_team_id=20)]
    goals = {1: {10: 1, 20: 0}}
    uc, repo = _make_use_case(fixtures=fixtures, goals=goals, competition_name="World Cup")
    result = await uc.execute(competition_id=350, season="2026", rules_version_id=3)

    assert result.skipped is False
    phases = {(a.team_id, a.phase) for a in repo.upserted}
    assert (10, "round_of_16") in phases
    assert (20, "round_of_32") in phases


@pytest.mark.anyio
async def test_semi_final_eliminated_teams_get_semi_final_phase():
    # 2 semis: teams 3,4 vs 1,2; final: 1 vs 3 (team 1 wins)
    fixtures = [
        KnockoutFixtureDTO(fixture_id=10, stage="semi", home_team_id=1, away_team_id=2),
        KnockoutFixtureDTO(fixture_id=11, stage="semi", home_team_id=3, away_team_id=4),
        KnockoutFixtureDTO(fixture_id=20, stage="final", home_team_id=1, away_team_id=3),
    ]
    goals = {20: {1: 2, 3: 0}}
    uc, repo = _make_use_case(fixtures=fixtures, goals=goals)
    result = await uc.execute(competition_id=10, season="2025", rules_version_id=3)
    assert result.skipped is False
    semi_teams = {a.team_id for a in repo.upserted if a.phase == "semi_final"}
    assert 2 in semi_teams
    assert 4 in semi_teams
    assert 1 not in semi_teams  # winner
    assert 3 not in semi_teams  # runner_up


@pytest.mark.anyio
async def test_full_tournament_all_phases_assigned():
    # round_of_16: 8 fixtures (16 teams, teams 1-16)
    # quarter: 4 fixtures (teams 1,3,5,7,9,11,13,15 advanced)
    # semi: 2 fixtures (teams 1,5,9,13)
    # final: 1 fixture (teams 1,9)
    r16_fixtures = [
        KnockoutFixtureDTO(fixture_id=i, stage="round_of_16", home_team_id=i * 2 - 1, away_team_id=i * 2)
        for i in range(1, 9)
    ]
    quarter_fixtures = [
        KnockoutFixtureDTO(fixture_id=10, stage="quarter", home_team_id=1, away_team_id=3),
        KnockoutFixtureDTO(fixture_id=11, stage="quarter", home_team_id=5, away_team_id=7),
        KnockoutFixtureDTO(fixture_id=12, stage="quarter", home_team_id=9, away_team_id=11),
        KnockoutFixtureDTO(fixture_id=13, stage="quarter", home_team_id=13, away_team_id=15),
    ]
    semi_fixtures = [
        KnockoutFixtureDTO(fixture_id=20, stage="semi", home_team_id=1, away_team_id=5),
        KnockoutFixtureDTO(fixture_id=21, stage="semi", home_team_id=9, away_team_id=13),
    ]
    final_fixture = [
        KnockoutFixtureDTO(fixture_id=30, stage="final", home_team_id=1, away_team_id=9),
    ]
    goals = {30: {1: 1, 9: 0}}
    all_fixtures = r16_fixtures + quarter_fixtures + semi_fixtures + final_fixture
    uc, repo = _make_use_case(fixtures=all_fixtures, goals=goals)
    result = await uc.execute(competition_id=10, season="2025", rules_version_id=3)
    assert result.skipped is False
    phase_counts = {}
    for a in repo.upserted:
        phase_counts[a.phase] = phase_counts.get(a.phase, 0) + 1
    assert phase_counts.get("round_of_16", 0) == 8   # teams 2,4,6,8,10,12,14,16
    assert phase_counts.get("quarter_final", 0) == 4  # teams 3,7,11,15
    assert phase_counts.get("semi_final", 0) == 2     # teams 5,13
    assert phase_counts.get("winner", 0) == 1         # team 1
    assert phase_counts.get("runner_up", 0) == 1      # team 9
    assert result.achievements_upserted == 16


@pytest.mark.anyio
async def test_unknown_competition_name_uses_zero_bonus_with_warning():
    fixtures = [KnockoutFixtureDTO(fixture_id=1, stage="final", home_team_id=1, away_team_id=2)]
    goals = {1: {1: 1, 2: 0}}
    uc, repo = _make_use_case(fixtures=fixtures, goals=goals, competition_name="Unknown Cup")
    result = await uc.execute(competition_id=999, season="2025", rules_version_id=3)
    assert result.skipped is False
    # Should still upsert achievements but with bonus_points=0
    assert result.achievements_upserted == 2
    for a in repo.upserted:
        assert a.bonus_points == 0
