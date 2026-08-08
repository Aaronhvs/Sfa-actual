from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from sfa.application.use_cases.get_ranking_explanations import (
    GetRankingExplanationsUseCase,
)
from sfa.domain.ports import RankedPlayerDTO
from sfa.domain.ranking_explanation_ports import (
    RankingExplanationEvidenceDTO,
    RankingExplanationRequestDTO,
    RankingExplanationWriteResultDTO,
    RankingPlayerExplanationDTO,
)
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.providers.ranking_explanation_writer import (
    DeterministicRankingExplanationWriter,
)
from sfa.infrastructure.repositories.ranking_explanation_repository import (
    _source_filter,
)


def _player(player_id: int, rank: int) -> RankedPlayerDTO:
    return RankedPlayerDTO(
        rank=rank,
        player_id=player_id,
        player_name=f"Player {player_id}",
        team_name="Club",
        team_logo_url=None,
        position="EXT",
        competition_name="Champions League",
        total_pts=1000.0 - rank,
        matches_played=10,
        photo_url=None,
    )


def _scope() -> AwardPeriodScope:
    return AwardPeriodScope(
        key="season-2025",
        label="2025/2026",
        kind=ScopeKind.AWARD_PERIOD,
        sources=(ScoreSource("2025", (2, 3)), ScoreSource("2026", (350,))),
        is_latest=True,
        includes_world_cup=True,
    )


class FakeScoreRepository:
    def __init__(self, players: list[RankedPlayerDTO]) -> None:
        self.players = players
        self.scope_calls: list[dict] = []

    async def resolve_rules_version_id_for_scope(self, scope, preferred):
        assert scope == _scope()
        return 4

    async def get_ranking_for_scope(self, **kwargs):
        self.scope_calls.append(kwargs)
        return self.players[: kwargs["limit"]]


class FakeSeasonRepository:
    async def resolve_scope(self, scope_key):
        assert scope_key == "season-2025"
        return _scope()


class FakeExplanationRepository:
    def __init__(self, cached=None) -> None:
        self.cached = cached or []
        self.cache_requests = []
        self.evidence_scopes = []

    async def get_cached_for_scope(self, request):
        self.cache_requests.append(request)
        return self.cached

    async def build_evidence(self, request, ranked_players, source_scope=None):
        self.evidence_scopes.append(source_scope)
        return [
            RankingExplanationEvidenceDTO(
                player_id=player.player_id,
                season=request.season,
                competition_id=request.competition_id,
                rules_version_id=request.rules_version_id,
                scope=request.scope,
                rank=player.rank,
                source_hash=f"hash-{player.player_id}",
                evidence={
                    "scope": {
                        "context_label": "Champions League",
                        "position": request.position,
                        "bonus_label": request.bonus_label,
                    },
                    "player": {
                        "id": player.player_id,
                        "name": player.player_name,
                        "rank": player.rank,
                        "total_pts": player.total_pts,
                    },
                },
            )
            for player in ranked_players
        ]


class FakeWriter:
    def __init__(self) -> None:
        self.player_ids = []

    async def write(self, evidence):
        self.player_ids.append(evidence.player_id)
        return RankingExplanationWriteResultDTO(
            short_text="Contextual short",
            long_text="Contextual long",
            bullets=[],
            variant="deterministic",
            status="fallback",
            model_name="fake",
        )


def _cached(player: RankedPlayerDTO) -> RankingPlayerExplanationDTO:
    return RankingPlayerExplanationDTO(
        id=player.player_id,
        player_id=player.player_id,
        player_name=player.player_name,
        team_name=player.team_name,
        team_logo_url=None,
        season="2025",
        competition_id=2,
        rules_version_id=4,
        scope="award_period",
        rank=player.rank,
        variant="ai",
        status="generated",
        short_text="Cached",
        long_text="Cached long",
        bullets=[],
        evidence={"player": {"total_pts": player.total_pts}},
        model_name="fake-ai",
        prompt_version="v1",
        generated_at=datetime.now(timezone.utc),
    )


@pytest.mark.anyio
async def test_builds_contextual_fallback_for_scope_and_filters():
    players = [_player(10, 1), _player(20, 2), _player(30, 3)]
    score_repo = FakeScoreRepository(players)
    explanation_repo = FakeExplanationRepository()
    writer = FakeWriter()
    use_case = GetRankingExplanationsUseCase(
        explanation_repo,
        score_repo=score_repo,
        season_repo=FakeSeasonRepository(),
        fallback_writer=writer,
    )
    request = RankingExplanationRequestDTO(
        season="2025",
        competition_id=2,
        rules_version_id=None,
        scope="award_period",
        scope_key="season-2025",
        position="EXT",
        bonus_label="Goleador",
        limit=3,
    )

    result = await use_case.execute(request)

    assert writer.player_ids == [10, 20, 30]
    assert explanation_repo.cache_requests == []
    assert explanation_repo.evidence_scopes == [_scope()]
    assert [item.player_id for item in result] == [10, 20, 30]
    assert all(item.id == 0 and item.status == "fallback" for item in result)
    assert score_repo.scope_calls[0]["competition_id"] == 2
    assert score_repo.scope_calls[0]["position"] == "EXT"
    assert score_repo.scope_calls[0]["bonus_label"] == "Goleador"
    assert score_repo.scope_calls[0]["rules_version_id"] == 4


@pytest.mark.anyio
async def test_reuses_complete_cache_for_unfiltered_context():
    players = [_player(10, 1), _player(20, 2), _player(30, 3)]
    score_repo = FakeScoreRepository(players)
    explanation_repo = FakeExplanationRepository([_cached(player) for player in players])
    writer = FakeWriter()
    use_case = GetRankingExplanationsUseCase(
        explanation_repo,
        score_repo=score_repo,
        season_repo=FakeSeasonRepository(),
        fallback_writer=writer,
    )

    result = await use_case.execute(
        RankingExplanationRequestDTO(
            season="2025",
            competition_id=2,
            rules_version_id=None,
            scope="award_period",
            scope_key="season-2025",
            limit=3,
        )
    )

    assert [item.short_text for item in result] == ["Cached", "Cached", "Cached"]
    assert writer.player_ids == []
    assert explanation_repo.cache_requests[0].rules_version_id == 4


@pytest.mark.anyio
async def test_rebuilds_fallback_when_cached_top_points_are_stale():
    players = [_player(10, 1), _player(20, 2), _player(30, 3)]
    stale = [_cached(player) for player in players]
    stale[0].evidence["player"]["total_pts"] = 1
    writer = FakeWriter()
    use_case = GetRankingExplanationsUseCase(
        FakeExplanationRepository(stale),
        score_repo=FakeScoreRepository(players),
        season_repo=FakeSeasonRepository(),
        fallback_writer=writer,
    )

    result = await use_case.execute(
        RankingExplanationRequestDTO(
            season="2025",
            competition_id=2,
            rules_version_id=None,
            scope="award_period",
            scope_key="season-2025",
            limit=3,
        )
    )

    assert writer.player_ids == [10, 20, 30]
    assert all(item.status == "fallback" for item in result)


def test_source_filter_contains_every_physical_scope_pair():
    expression = _source_filter(
        SFASeasonScore.season,
        SFASeasonScore.competition_id,
        _scope(),
    )

    sql = str(
        expression.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "sfa_season_scores.season = '2025'" in sql
    assert "sfa_season_scores.competition_id IN (2, 3)" in sql
    assert "sfa_season_scores.season = '2026'" in sql
    assert "sfa_season_scores.competition_id IN (350)" in sql


@pytest.mark.anyio
async def test_deterministic_writer_names_visible_filter_context():
    evidence = RankingExplanationEvidenceDTO(
        player_id=10,
        season="2025",
        competition_id=2,
        rules_version_id=4,
        scope="award_period",
        rank=1,
        source_hash="hash",
        evidence={
            "scope": {
                "context_label": "Champions League",
                "position": "EXT",
                "bonus_label": None,
            },
            "player": {
                "id": 10,
                "name": "Player 10",
                "rank": 1,
                "total_pts": 999,
                "matches": 10,
                "goals": 5,
            },
        },
    )

    result = await DeterministicRankingExplanationWriter().write(evidence)

    assert "Champions League" in result.short_text
    assert "entre jugadores EXT" in result.long_text
