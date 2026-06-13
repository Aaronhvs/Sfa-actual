from sfa.application.use_cases.get_player_achievements import (
    GetPlayerAchievementsUseCase,
)
from sfa.domain.scoring_ports import PlayerCompetitionAchievementDTO


class FakeAchievementRepository:
    def __init__(self) -> None:
        self.received_season: str | None = "unset"
        self.received_rules_version_id: int | None = None

    async def get_player_achievements(
        self,
        player_id: int,
        rules_version_id: int,
        season: str | None = None,
    ) -> list[PlayerCompetitionAchievementDTO]:
        self.received_season = season
        self.received_rules_version_id = rules_version_id
        if player_id == 0:
            return []
        return [
            PlayerCompetitionAchievementDTO(
                achievement_id=1,
                competition_id=10,
                competition_name="Champions League",
                team_id=1,
                team_name="Barcelona",
                season="2024",
                phase="semi_final",
                title_count=0,
                bonus_pts=145.5,
            )
        ]


async def test_all_is_normalized_to_no_season_filter():
    repository = FakeAchievementRepository()
    result = await GetPlayerAchievementsUseCase(
        repository, default_rules_version_id=3
    ).execute(52, "all")

    assert repository.received_season is None
    assert repository.received_rules_version_id == 3
    assert result[0].phase == "semi_final"
    assert result[0].bonus_pts == 145.5


async def test_concrete_season_is_preserved():
    repository = FakeAchievementRepository()
    await GetPlayerAchievementsUseCase(
        repository, default_rules_version_id=3
    ).execute(52, "2024", rules_version_id=4)

    assert repository.received_season == "2024"
    assert repository.received_rules_version_id == 4


async def test_empty_achievements_are_valid():
    repository = FakeAchievementRepository()

    assert await GetPlayerAchievementsUseCase(
        repository, default_rules_version_id=3
    ).execute(0, "2024") == []


async def test_missing_rules_version_returns_empty_without_querying_repository():
    repository = FakeAchievementRepository()

    assert await GetPlayerAchievementsUseCase(repository).execute(52, "2024") == []
    assert repository.received_rules_version_id is None
