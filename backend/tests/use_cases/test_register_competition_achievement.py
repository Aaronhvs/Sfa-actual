from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.register_competition_achievement import (
    RegisterCompetitionAchievementUseCase,
)
from sfa.domain.scoring.entities import CompetitionAchievement, ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import CompetitionAchievementRepositoryPort, ScoringRulesVersionRepositoryPort


class FakeScoringRulesVersionRepository(ScoringRulesVersionRepositoryPort):
    def __init__(self, version: ScoringRulesVersion | None = None):
        self._version = version

    async def get_active_version(self): return self._version
    async def get_version_by_id(self, version_id: int):
        return self._version if (self._version and self._version.id == version_id) else None
    async def list_versions(self): return [self._version] if self._version else []
    async def save_version(self, name, version, description, config) -> int: return 1
    async def set_active_version(self, version_id: int) -> None: pass


class FakeCompetitionAchievementRepository(CompetitionAchievementRepositoryPort):
    def __init__(self):
        self.achievements: list[CompetitionAchievement] = []
        self._next_id = 1

    async def upsert_achievement(self, achievement: CompetitionAchievement) -> int:
        existing = next(
            (a for a in self.achievements
             if a.competition_id == achievement.competition_id
             and a.team_id == achievement.team_id
             and a.season == achievement.season
             and a.phase == achievement.phase),
            None
        )
        if existing:
            self.achievements.remove(existing)
        new_ach = CompetitionAchievement(
            id=self._next_id, competition_id=achievement.competition_id,
            team_id=achievement.team_id, season=achievement.season,
            phase=achievement.phase, bonus_points=achievement.bonus_points,
            weight=achievement.weight, created_at=datetime.now(timezone.utc),
        )
        self.achievements.append(new_ach)
        self._next_id += 1
        return new_ach.id

    async def get_achievements_for_season(self, competition_id, season): return []
    async def upsert_player_bonus(self, bonus): pass
    async def get_team_total_minutes(self, team_id, competition_id, season): return 0
    async def get_player_minutes_in_competition(self, player_id, competition_id, season): return 0
    async def get_players_for_team_season(self, team_id, competition_id, season): return []
    async def update_season_score_bonus(self, player_id, competition_id, season, rules_version_id, bonus_pts): pass
    async def get_player_rank_in_team(self, player_id, team_id, competition_id, season, rules_version_id): return 12
    async def get_player_avg_rating(self, player_id, competition_id, season): return None
    async def get_competition_ids_for_season(self, season): return []


def _make_version() -> ScoringRulesVersion:
    return ScoringRulesVersion(
        id=1, name="v2-test", version="2.0.0", description="",
        is_active=True, config=ScoringConfig.default_v2(),
        created_at=datetime.now(timezone.utc),
    )


class TestRegisterCompetitionAchievementUseCase:
    @pytest.mark.anyio
    async def test_valid_phase_creates_achievement(self):
        version = _make_version()
        ach_repo = FakeCompetitionAchievementRepository()
        use_case = RegisterCompetitionAchievementUseCase(
            ach_repo, FakeScoringRulesVersionRepository(version)
        )

        result = await use_case.execute(
            competition_id=2, team_id=5, season="2024",
            phase="winner", rules_version_id=1,
        )

        assert result.status == "registered"
        assert result.achievement_id > 0
        assert len(ach_repo.achievements) == 1
        assert ach_repo.achievements[0].phase == "winner"

    @pytest.mark.anyio
    async def test_invalid_phase_returns_failed(self):
        version = _make_version()
        ach_repo = FakeCompetitionAchievementRepository()
        use_case = RegisterCompetitionAchievementUseCase(
            ach_repo, FakeScoringRulesVersionRepository(version)
        )

        result = await use_case.execute(
            competition_id=2, team_id=5, season="2024",
            phase="invented_phase_xyz", rules_version_id=1,
        )

        assert result.status == "failed"
        assert result.error is not None
        assert len(ach_repo.achievements) == 0

    @pytest.mark.anyio
    async def test_duplicate_phase_upserts_not_duplicates(self):
        version = _make_version()
        ach_repo = FakeCompetitionAchievementRepository()
        use_case = RegisterCompetitionAchievementUseCase(
            ach_repo, FakeScoringRulesVersionRepository(version)
        )

        await use_case.execute(competition_id=2, team_id=5, season="2024",
                               phase="winner", rules_version_id=1)
        await use_case.execute(competition_id=2, team_id=5, season="2024",
                               phase="winner", rules_version_id=1)

        assert len(ach_repo.achievements) == 1  # upsert, not duplicate

    @pytest.mark.anyio
    async def test_nonexistent_rules_version_returns_failed(self):
        ach_repo = FakeCompetitionAchievementRepository()
        use_case = RegisterCompetitionAchievementUseCase(
            ach_repo, FakeScoringRulesVersionRepository(None)
        )

        result = await use_case.execute(
            competition_id=2, team_id=5, season="2024",
            phase="winner", rules_version_id=999,
        )

        assert result.status == "failed"
        assert "not found" in (result.error or "").lower()
