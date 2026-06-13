import pytest

from sfa.application.use_cases.get_seasons import GetSeasonsUseCase, SeasonsResult
from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol


class FakeSeasonRepository(SeasonRepositoryProtocol):
    def __init__(self, seasons: list[SeasonDTO] | None = None):
        self._seasons = seasons or []

    async def get_available_seasons(self) -> list[SeasonDTO]:
        return self._seasons


class TestGetSeasons:
    @pytest.mark.anyio
    async def test_returns_seasons_list(self):
        seasons = [SeasonDTO("2025", True), SeasonDTO("2024", False)]
        result = await GetSeasonsUseCase(FakeSeasonRepository(seasons)).execute()

        assert isinstance(result, SeasonsResult)
        assert len(result.seasons) == 2
        assert result.seasons[0].season == "2025"
        assert result.seasons[0].is_latest is True

    @pytest.mark.anyio
    async def test_returns_empty_when_no_seasons(self):
        result = await GetSeasonsUseCase(FakeSeasonRepository()).execute()

        assert result.seasons == []

    @pytest.mark.anyio
    async def test_fake_isinstance_protocol(self):
        assert isinstance(FakeSeasonRepository(), SeasonRepositoryProtocol)
