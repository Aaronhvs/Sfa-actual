from __future__ import annotations

import pytest

from sfa.application.use_cases.enrich_player_positions import EnrichPlayerPositionsUseCase
from sfa.domain.transfermarkt_ports import (
    EnrichPositionRepositoryPort,
    PlayerForEnrichDTO,
    PlayerTmIdRepositoryPort,
    PlayerTmIdRow,
    TmPlayerData,
    TmSearchResult,
    TransfermarktProviderPort,
)
from sfa.infrastructure.models.enums import Position


class FakeTransfermarktProvider(TransfermarktProviderPort):
    def __init__(
        self,
        search_result: TmSearchResult | None = None,
        position_data: TmPlayerData | None = None,
    ) -> None:
        self._search = search_result
        self._position = position_data
        self.search_calls = 0

    async def search_player(self, name: str, team_name: str) -> TmSearchResult | None:
        self.search_calls += 1
        return self._search

    async def fetch_player_position(self, tm_id: int, slug: str) -> TmPlayerData | None:
        return self._position


class FakePlayerTmIdRepo(PlayerTmIdRepositoryPort):
    def __init__(self) -> None:
        self.stored: dict[int, PlayerTmIdRow] = {}

    async def get_tm_id(self, player_id: int) -> PlayerTmIdRow | None:
        return self.stored.get(player_id)

    async def upsert_tm_id(self, player_id: int, tm_id: int, verified: bool) -> None:
        self.stored[player_id] = PlayerTmIdRow(player_id=player_id, tm_id=tm_id, verified=verified)


class FakeEnrichPositionRepo(EnrichPositionRepositoryPort):
    def __init__(self, players: list[PlayerForEnrichDTO]) -> None:
        self._players = players
        self.updates: list[tuple[int, Position, str]] = []

    async def get_players_without_tm_source(self, limit: int) -> list[PlayerForEnrichDTO]:
        return self._players[:limit]

    async def update_player_position(
        self, player_id: int, position: Position, source: str,
    ) -> None:
        self.updates.append((player_id, position, source))


class TestEnrichPlayerPositionsUseCase:
    @pytest.mark.anyio
    async def test_successful_enrichment_updates_position(self):
        player = PlayerForEnrichDTO(
            id=1, name="Vitinha", team_name="Paris Saint-Germain", position_source="apifootball"
        )
        search = TmSearchResult(tm_id=388282, name="Vitinha", team_name="Paris Saint-Germain", slug="vitinha")
        pos_data = TmPlayerData(tm_id=388282, position_raw="Central Midfield", position_mapped=Position.MC)
        enrich_repo = FakeEnrichPositionRepo([player])

        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(search_result=search, position_data=pos_data),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=enrich_repo,
            rate_limit_seconds=0.0,
        )
        result = await use_case.execute(batch_size=10)

        assert result.matched == 1
        assert result.position_updated == 1
        assert result.unmatched == 0
        assert result.failed == 0
        assert result.skipped_already_tm == 0
        assert enrich_repo.updates == [(1, Position.MC, "transfermarkt")]

    @pytest.mark.anyio
    async def test_updates_with_mco_for_attacking_midfield(self):
        player = PlayerForEnrichDTO(
            id=2, name="Bruno Fernandes", team_name="Manchester United", position_source="apifootball"
        )
        search = TmSearchResult(
            tm_id=240306, name="Bruno Fernandes", team_name="Manchester United", slug="bruno-fernandes"
        )
        pos_data = TmPlayerData(tm_id=240306, position_raw="Attacking Midfield", position_mapped=Position.MCO)
        enrich_repo = FakeEnrichPositionRepo([player])

        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(search_result=search, position_data=pos_data),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=enrich_repo,
            rate_limit_seconds=0.0,
        )
        result = await use_case.execute(batch_size=10)

        assert result.position_updated == 1
        assert enrich_repo.updates[0] == (2, Position.MCO, "transfermarkt")

    @pytest.mark.anyio
    async def test_unmatched_player_increments_counter(self):
        player = PlayerForEnrichDTO(
            id=3, name="Unknown Player", team_name="Unknown FC", position_source="apifootball"
        )
        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(search_result=None, position_data=None),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=FakeEnrichPositionRepo([player]),
            rate_limit_seconds=0.0,
        )
        result = await use_case.execute(batch_size=10)

        assert result.unmatched == 1
        assert result.matched == 0
        assert result.position_updated == 0

    @pytest.mark.anyio
    async def test_cached_tm_id_skips_search(self):
        player = PlayerForEnrichDTO(
            id=4, name="Virgil van Dijk", team_name="Liverpool", position_source="apifootball"
        )
        pos_data = TmPlayerData(tm_id=139208, position_raw="Centre-Back", position_mapped=Position.DC)
        provider = FakeTransfermarktProvider(search_result=None, position_data=pos_data)
        tm_id_repo = FakePlayerTmIdRepo()
        await tm_id_repo.upsert_tm_id(4, 139208, verified=True)
        enrich_repo = FakeEnrichPositionRepo([player])

        use_case = EnrichPlayerPositionsUseCase(
            provider=provider,
            tm_id_repo=tm_id_repo,
            enrich_repo=enrich_repo,
            rate_limit_seconds=0.0,
        )
        result = await use_case.execute(batch_size=10)

        assert result.matched == 1
        assert result.position_updated == 1
        assert provider.search_calls == 0
        assert enrich_repo.updates[0] == (4, Position.DC, "transfermarkt")

    @pytest.mark.anyio
    async def test_skips_players_already_from_transfermarkt(self):
        player = PlayerForEnrichDTO(
            id=5, name="Already Enriched", team_name="FC Barcelona", position_source="transfermarkt"
        )
        enrich_repo = FakeEnrichPositionRepo([player])
        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=enrich_repo,
            rate_limit_seconds=0.0,
        )
        result = await use_case.execute(batch_size=10)

        assert result.skipped_already_tm == 1
        assert result.matched == 0
        assert len(enrich_repo.updates) == 0

    @pytest.mark.anyio
    async def test_failed_player_increments_counter_and_continues(self):
        class BrokenProvider(TransfermarktProviderPort):
            async def search_player(self, name: str, team_name: str) -> TmSearchResult | None:
                raise RuntimeError("Network error")

            async def fetch_player_position(self, tm_id: int, slug: str) -> TmPlayerData | None:
                return None

        player = PlayerForEnrichDTO(id=6, name="Error Player", team_name="FC Error", position_source="apifootball")
        use_case = EnrichPlayerPositionsUseCase(
            provider=BrokenProvider(),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=FakeEnrichPositionRepo([player]),
            rate_limit_seconds=0.0,
        )
        result = await use_case.execute(batch_size=10)

        assert result.failed == 1
        assert result.matched == 0

    @pytest.mark.anyio
    async def test_result_total_reflects_batch(self):
        players = [
            PlayerForEnrichDTO(id=i, name=f"Player {i}", team_name="FC Test", position_source="apifootball")
            for i in range(5)
        ]
        use_case = EnrichPlayerPositionsUseCase(
            provider=FakeTransfermarktProvider(search_result=None),
            tm_id_repo=FakePlayerTmIdRepo(),
            enrich_repo=FakeEnrichPositionRepo(players),
            rate_limit_seconds=0.0,
        )
        result = await use_case.execute(batch_size=3)

        assert result.total_processed == 3
