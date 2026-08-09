from dataclasses import replace
from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.infer_league_champions import (
    InferLeagueChampionsUseCase,
)
from sfa.domain.scoring.entities import CompetitionAchievement, ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import LeagueChampionCandidateDTO
from tests.use_cases.test_calculate_scores_for_rules_version import (
    FakeScoringRulesVersionRepository,
)
from tests.use_cases.test_scoring_balance_v2 import (
    FakeCompetitionAchievementRepository,
)


def _make_version(config: ScoringConfig | None = None) -> ScoringRulesVersion:
    return ScoringRulesVersion(
        id=4,
        name="v4-test",
        version="4.0",
        description="",
        is_active=True,
        config=config or ScoringConfig.default_v2(),
        created_at=datetime.now(timezone.utc),
    )


def _leader(
    competition_id: int = 39,
    competition_name: str = "Premier League",
    team_id: int = 10,
    matchday: int = 38,
    team_count: int = 20,
    regular_fixture_count: int = 380,
    pending_fixture_count: int = 0,
) -> LeagueChampionCandidateDTO:
    return LeagueChampionCandidateDTO(
        competition_id=competition_id,
        competition_name=competition_name,
        team_id=team_id,
        season="2025",
        matchday=matchday,
        team_count=team_count,
        regular_fixture_count=regular_fixture_count,
        pending_fixture_count=pending_fixture_count,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("candidate", "expected_team"),
    [
        (_leader(), 10),
        (_leader(61, "Ligue 1", 20, 34, 18, 306), 20),
    ],
)
async def test_infers_champion_from_completed_domestic_league(candidate, expected_team):
    repo = FakeCompetitionAchievementRepository(league_leaders=[candidate])
    use_case = InferLeagueChampionsUseCase(
        achievement_repo=repo,
        rules_version_repo=FakeScoringRulesVersionRepository(_make_version()),
    )

    result = await use_case.execute(season="2025", rules_version_id=4)

    assert result.status == "completed"
    assert result.champions_inferred == 1
    assert result.candidates_skipped == 0
    assert len(repo.replaced_achievements) == 1
    achievement = repo.replaced_achievements[0]
    assert achievement.team_id == expected_team
    assert achievement.phase == "champion"
    assert achievement.bonus_points == 7000


@pytest.mark.anyio
async def test_skips_leader_when_domestic_league_is_not_complete():
    repo = FakeCompetitionAchievementRepository(
        league_leaders=[_leader(matchday=37)]
    )
    use_case = InferLeagueChampionsUseCase(
        achievement_repo=repo,
        rules_version_repo=FakeScoringRulesVersionRepository(_make_version()),
    )

    result = await use_case.execute(season="2025", rules_version_id=4)

    assert result.champions_inferred == 0
    assert result.candidates_skipped == 1
    assert repo.replaced_achievements == []


@pytest.mark.anyio
async def test_skips_leader_when_a_regular_fixture_is_still_pending():
    repo = FakeCompetitionAchievementRepository(
        league_leaders=[_leader(pending_fixture_count=1)]
    )
    use_case = InferLeagueChampionsUseCase(
        achievement_repo=repo,
        rules_version_repo=FakeScoringRulesVersionRepository(_make_version()),
    )

    result = await use_case.execute(season="2025", rules_version_id=4)

    assert result.champions_inferred == 0
    assert result.candidates_skipped == 1
    assert repo.replaced_achievements == []


@pytest.mark.anyio
async def test_replaces_stale_champion_for_same_league_season():
    stale = CompetitionAchievement(
        id=1,
        competition_id=39,
        team_id=99,
        season="2025",
        phase="champion",
        bonus_points=7000,
        weight=1.0,
        created_at=datetime.now(timezone.utc),
    )
    repo = FakeCompetitionAchievementRepository(
        achievements=[stale],
        league_leaders=[_leader(team_id=10)],
    )
    use_case = InferLeagueChampionsUseCase(
        achievement_repo=repo,
        rules_version_repo=FakeScoringRulesVersionRepository(_make_version()),
    )

    await use_case.execute(season="2025", rules_version_id=4)

    champions = [
        achievement for achievement in repo._achievements
        if achievement.competition_id == 39 and achievement.phase == "champion"
    ]
    assert len(champions) == 1
    assert champions[0].team_id == 10


@pytest.mark.anyio
async def test_no_op_when_champion_bonus_is_not_configured():
    config = ScoringConfig.default_v2()
    bonuses = {key: dict(value) for key, value in config.achievement_phase_bonuses.items()}
    bonuses["domestic_league"].pop("champion")
    config = replace(config, achievement_phase_bonuses=bonuses)
    repo = FakeCompetitionAchievementRepository(league_leaders=[_leader()])
    use_case = InferLeagueChampionsUseCase(
        achievement_repo=repo,
        rules_version_repo=FakeScoringRulesVersionRepository(_make_version(config)),
    )

    result = await use_case.execute(season="2025", rules_version_id=4)

    assert result.status == "completed"
    assert result.candidates_found == 0
    assert repo.replaced_achievements == []


@pytest.mark.anyio
async def test_fails_when_rules_version_does_not_exist():
    repo = FakeCompetitionAchievementRepository(league_leaders=[_leader()])
    use_case = InferLeagueChampionsUseCase(
        achievement_repo=repo,
        rules_version_repo=FakeScoringRulesVersionRepository(None),
    )

    result = await use_case.execute(season="2025", rules_version_id=999)

    assert result.status == "failed"
    assert "999" in (result.error or "")
    assert repo.replaced_achievements == []
