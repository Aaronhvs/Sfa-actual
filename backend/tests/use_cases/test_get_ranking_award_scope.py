import pytest

from sfa.application.use_cases.get_ranking import GetRankingUseCase
from sfa.domain.ports import RankedPlayerDTO, SeasonDTO
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource


class FakeSeasonRepository:
    def __init__(self, scope):
        self.scope = scope

    async def resolve_scope(self, scope_key=None):
        return self.scope

    async def get_available_seasons(self):
        return [SeasonDTO("2025", True, key="season-2025", label="2025/2026")]

    async def get_available_scopes_for_player(self, player_id):
        return await self.get_available_seasons()


class FakeScopeScoreRepository:
    def __init__(self, player):
        self.player = player
        self.scope = None
        self.version = None

    async def resolve_rules_version_id_for_scope(self, scope, preferred_rules_version_id=None):
        self.scope = scope
        return preferred_rules_version_id or 7

    async def get_ranking_for_scope(self, scope, *args):
        self.version = args[-2]
        return [self.player]

    async def get_ranking_total_for_scope(self, scope, *args):
        return 1


@pytest.mark.anyio
async def test_default_ranking_uses_latest_award_scope():
    scope = AwardPeriodScope(
        key="season-2025",
        label="2025/2026",
        kind=ScopeKind.AWARD_PERIOD,
        sources=(ScoreSource("2025", (1,)), ScoreSource("2026", (350,))),
        is_latest=True,
        includes_world_cup=True,
    )
    player = RankedPlayerDTO(
        rank=1,
        player_id=10,
        player_name="Player",
        team_name="Club",
        team_logo_url=None,
        position="DEL",
        competition_name="League",
        total_pts=1234.0,
        matches_played=30,
        photo_url=None,
    )
    score_repo = FakeScopeScoreRepository(player)
    use_case = GetRankingUseCase(
        score_repo,
        default_rules_version_id=7,
        season_repo=FakeSeasonRepository(scope),
    )

    result = await use_case.execute(use_total=True)

    assert result.scope == "season-2025"
    assert result.season == "2025"
    assert result.ranking == [player]
    assert score_repo.scope.sources[1].competition_ids == (350,)
