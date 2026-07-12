import pytest

from sfa.application.use_cases.generate_ranking_explanations import (
    GenerateRankingExplanationsUseCase,
)
from sfa.domain.ports import RankedPlayerDTO
from sfa.domain.ranking_explanation_ports import (
    RankingExplanationEvidenceDTO,
    RankingExplanationRequestDTO,
    RankingExplanationWriteResultDTO,
)


def _ranked(player_id: int, rank: int) -> RankedPlayerDTO:
    return RankedPlayerDTO(
        rank=rank,
        player_id=player_id,
        player_name=f"Player {player_id}",
        team_name="Team",
        team_logo_url=None,
        position="DEL",
        competition_name="World Cup",
        total_pts=1000.0 - rank,
        matches_played=3,
        photo_url=None,
        goals=rank,
        assists=0,
    )


class FakeScoreRepository:
    def __init__(self, players: list[RankedPlayerDTO]) -> None:
        self.players = players
        self.calls = []

    async def get_ranking(self, **kwargs):
        self.calls.append(kwargs)
        return self.players[: kwargs["limit"]]


class FakeExplanationRepository:
    def __init__(self, existing_hashes: dict[int, str] | None = None) -> None:
        self.existing_hashes = existing_hashes or {}
        self.upserted: list[tuple[int, str]] = []
        self.stale_requests = []

    async def build_evidence(self, request, ranked_players):
        return [
            RankingExplanationEvidenceDTO(
                player_id=player.player_id,
                season=request.season,
                competition_id=request.competition_id,
                rules_version_id=request.rules_version_id,
                scope=request.scope,
                rank=player.rank,
                source_hash=f"hash-{player.player_id}-rank-{player.rank}-pts-{player.total_pts}",
                evidence={
                    "player": {
                        "id": player.player_id,
                        "rank": player.rank,
                        "total_pts": player.total_pts,
                    }
                },
            )
            for player in ranked_players
        ]

    async def mark_stale_for_scope(self, request, fresh_hashes):
        self.stale_requests.append((request, fresh_hashes))
        return 0

    async def get_source_hash(self, player_id, request):
        return self.existing_hashes.get(player_id)

    async def upsert_explanation(self, evidence, result, prompt_version):
        self.upserted.append((evidence.player_id, prompt_version))


class FakeWriter:
    def __init__(self) -> None:
        self.player_ids: list[int] = []

    async def write(self, evidence):
        self.player_ids.append(evidence.player_id)
        return RankingExplanationWriteResultDTO(
            short_text="short",
            long_text="long",
            bullets=[],
            variant="ai",
            status="generated",
            model_name="fake",
        )


class FailingWriter:
    async def write(self, evidence):
        raise RuntimeError("provider down")


def _request(limit: int = 3, force: bool = False) -> RankingExplanationRequestDTO:
    return RankingExplanationRequestDTO(
        season="2026",
        competition_id=350,
        rules_version_id=4,
        scope="world_cup",
        limit=limit,
        use_total=True,
        force=force,
    )


@pytest.mark.anyio
async def test_generates_only_new_top_player_and_skips_unchanged_players():
    players = [_ranked(10, 1), _ranked(20, 2), _ranked(30, 3)]
    existing_hashes = {
        10: "hash-10-rank-1-pts-999.0",
        20: "hash-20-rank-2-pts-998.0",
    }
    score_repo = FakeScoreRepository(players)
    explanation_repo = FakeExplanationRepository(existing_hashes)
    writer = FakeWriter()
    use_case = GenerateRankingExplanationsUseCase(score_repo, explanation_repo, writer)

    result = await use_case.execute(_request())

    assert writer.player_ids == [30]
    assert explanation_repo.upserted == [(30, "ranking-v8-action-relevance")]
    assert result.generated == 1
    assert result.skipped == 2
    assert result.fallback == 0
    assert result.failed == 0


@pytest.mark.anyio
async def test_regenerates_only_player_with_changed_context_hash():
    players = [_ranked(10, 1), _ranked(20, 2), _ranked(30, 3)]
    existing_hashes = {
        10: "hash-10-rank-1-pts-999.0",
        20: "old-hash-for-player-20",
        30: "hash-30-rank-3-pts-997.0",
    }
    score_repo = FakeScoreRepository(players)
    explanation_repo = FakeExplanationRepository(existing_hashes)
    writer = FakeWriter()
    use_case = GenerateRankingExplanationsUseCase(score_repo, explanation_repo, writer)

    result = await use_case.execute(_request())

    assert writer.player_ids == [20]
    assert explanation_repo.upserted == [(20, "ranking-v8-action-relevance")]
    assert result.generated == 1
    assert result.skipped == 2


@pytest.mark.anyio
async def test_skips_everything_when_top_players_are_unchanged():
    players = [_ranked(10, 1), _ranked(20, 2), _ranked(30, 3)]
    existing_hashes = {
        player.player_id: f"hash-{player.player_id}-rank-{player.rank}-pts-{player.total_pts}"
        for player in players
    }
    score_repo = FakeScoreRepository(players)
    explanation_repo = FakeExplanationRepository(existing_hashes)
    writer = FakeWriter()
    use_case = GenerateRankingExplanationsUseCase(score_repo, explanation_repo, writer)

    result = await use_case.execute(_request())

    assert writer.player_ids == []
    assert explanation_repo.upserted == []
    assert result.generated == 0
    assert result.skipped == 3
    assert explanation_repo.stale_requests == [
        (
            _request(),
            {
                10: "hash-10-rank-1-pts-999.0",
                20: "hash-20-rank-2-pts-998.0",
                30: "hash-30-rank-3-pts-997.0",
            },
        )
    ]


@pytest.mark.anyio
async def test_rank_change_changes_hash_and_regenerates_that_player():
    player = _ranked(10, 2)
    score_repo = FakeScoreRepository([player])
    explanation_repo = FakeExplanationRepository(
        {10: "hash-10-rank-1-pts-998.0"}
    )
    writer = FakeWriter()
    use_case = GenerateRankingExplanationsUseCase(score_repo, explanation_repo, writer)

    result = await use_case.execute(_request(limit=1))

    assert writer.player_ids == [10]
    assert result.generated == 1
    assert result.skipped == 0


@pytest.mark.anyio
async def test_force_regenerates_even_when_hash_is_unchanged():
    players = [_ranked(10, 1), _ranked(20, 2)]
    existing_hashes = {
        player.player_id: f"hash-{player.player_id}-rank-{player.rank}-pts-{player.total_pts}"
        for player in players
    }
    score_repo = FakeScoreRepository(players)
    explanation_repo = FakeExplanationRepository(existing_hashes)
    writer = FakeWriter()
    use_case = GenerateRankingExplanationsUseCase(score_repo, explanation_repo, writer)

    result = await use_case.execute(_request(limit=2, force=True))

    assert writer.player_ids == [10, 20]
    assert result.generated == 2
    assert result.skipped == 0


@pytest.mark.anyio
async def test_writer_error_falls_back_without_stopping_generation():
    players = [_ranked(10, 1)]
    score_repo = FakeScoreRepository(players)
    explanation_repo = FakeExplanationRepository()
    use_case = GenerateRankingExplanationsUseCase(
        score_repo,
        explanation_repo,
        FailingWriter(),
    )

    result = await use_case.execute(_request(limit=1))

    assert explanation_repo.upserted == [(10, "ranking-v8-action-relevance")]
    assert result.generated == 0
    assert result.fallback == 1
    assert result.failed == 0
    assert result.skipped == 0
