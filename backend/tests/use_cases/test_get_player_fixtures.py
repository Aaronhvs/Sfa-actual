# Baseline before this spec (0004): 43 passed, 0 failed (unrelated to fixtures).
# The 3 existing fixture tests were green before this spec.
import datetime as dt

import pytest

from sfa.application.use_cases.get_player_fixtures import GetPlayerFixturesUseCase
from sfa.domain.ports import (
    FixtureActionBreakdown,
    PlayerEventRepositoryProtocol,
    PlayerFixtureDTO,
)


class FakePlayerEventRepository(PlayerEventRepositoryProtocol):
    def __init__(
        self,
        fixtures: list[PlayerFixtureDTO] | None = None,
        breakdown_map: dict[int, dict[str, FixtureActionBreakdown]] | None = None,
    ):
        self._fixtures = fixtures or []
        self._breakdown_map = breakdown_map or {}
        self.last_fixtures_call: dict = {}
        self.breakdown_call_count: int = 0

    async def get_events_by_player(self, player_id, season=None, competition_id=None):
        return []

    async def get_fixtures_by_player(
        self,
        player_id,
        season=None,
        competition_id=None,
        competition_name=None,
        rival=None,
        date=None,
    ):
        self.last_fixtures_call = {
            "player_id": player_id,
            "season": season,
            "competition_id": competition_id,
            "competition_name": competition_name,
            "rival": rival,
            "date": date,
        }
        return self._fixtures

    async def get_fixture_breakdown_by_player(self, player_id, fixture_ids):
        self.breakdown_call_count += 1
        return self._breakdown_map


def _make_fixture(fixture_id: int = 1) -> PlayerFixtureDTO:
    return PlayerFixtureDTO(
        fixture_id=fixture_id,
        competition="Liga",
        stage="Regular",
        home_team="Team A",
        away_team="Team B",
        played_at=dt.datetime(2024, 10, 1, 15, 0),
        sfa_pts=75.0,
        events_count=3,
    )


class TestGetPlayerFixtures:
    @pytest.mark.anyio
    async def test_returns_fixtures(self):
        fixture = _make_fixture()
        repo = FakePlayerEventRepository(fixtures=[fixture], breakdown_map={})
        uc = GetPlayerFixturesUseCase(repo)

        result = await uc.execute(player_id=1, include_breakdown=False)

        assert len(result) == 1
        assert result[0].fixture_id == 1
        assert result[0].sfa_pts == 75.0

    @pytest.mark.anyio
    async def test_returns_empty_list(self):
        repo = FakePlayerEventRepository(fixtures=[])
        uc = GetPlayerFixturesUseCase(repo)

        result = await uc.execute(player_id=99, include_breakdown=False)

        assert result == []

    @pytest.mark.anyio
    async def test_passes_filters(self):
        repo = FakePlayerEventRepository(fixtures=[])
        uc = GetPlayerFixturesUseCase(repo)

        await uc.execute(player_id=7, season="2024-25", competition_id=2, include_breakdown=False)

        assert repo.last_fixtures_call["player_id"] == 7
        assert repo.last_fixtures_call["season"] == "2024-25"
        assert repo.last_fixtures_call["competition_id"] == 2

    @pytest.mark.anyio
    async def test_fixtures_with_breakdown_returns_breakdown_per_fixture(self):
        f1 = _make_fixture(fixture_id=101)
        f2 = _make_fixture(fixture_id=102)
        breakdown_map = {
            101: {"goal": FixtureActionBreakdown(count=1, pts=320.5)},
            102: {"stats": FixtureActionBreakdown(count=1, pts=85.0)},
        }
        repo = FakePlayerEventRepository(fixtures=[f1, f2], breakdown_map=breakdown_map)
        uc = GetPlayerFixturesUseCase(repo)

        result = await uc.execute(player_id=1, include_breakdown=True)

        assert result[0].breakdown is not None
        assert result[0].breakdown["goal"].count == 1
        assert result[1].breakdown is not None
        assert result[1].breakdown["stats"].pts == 85.0

    @pytest.mark.anyio
    async def test_fixtures_without_breakdown_skips_second_query(self):
        repo = FakePlayerEventRepository(fixtures=[_make_fixture()])
        uc = GetPlayerFixturesUseCase(repo)

        result = await uc.execute(player_id=1, include_breakdown=False)

        assert repo.breakdown_call_count == 0
        assert result[0].breakdown is None

    @pytest.mark.anyio
    async def test_fixtures_empty_list_skips_breakdown_query(self):
        repo = FakePlayerEventRepository(fixtures=[])
        uc = GetPlayerFixturesUseCase(repo)

        result = await uc.execute(player_id=1, include_breakdown=True)

        assert repo.breakdown_call_count == 0
        assert result == []

    @pytest.mark.anyio
    async def test_fixtures_rival_filter_passed_to_repo(self):
        repo = FakePlayerEventRepository(fixtures=[])
        uc = GetPlayerFixturesUseCase(repo)

        await uc.execute(player_id=1, rival="Barcelona", include_breakdown=False)

        assert repo.last_fixtures_call["rival"] == "Barcelona"

    @pytest.mark.anyio
    async def test_fixtures_date_filter_passed_to_repo(self):
        repo = FakePlayerEventRepository(fixtures=[])
        uc = GetPlayerFixturesUseCase(repo)

        await uc.execute(player_id=1, date=dt.date(2024, 11, 3), include_breakdown=False)

        assert repo.last_fixtures_call["date"] == dt.date(2024, 11, 3)

    @pytest.mark.anyio
    async def test_fixtures_competition_name_filter_passed_to_repo(self):
        repo = FakePlayerEventRepository(fixtures=[])
        uc = GetPlayerFixturesUseCase(repo)

        await uc.execute(player_id=1, competition_name="Champions", include_breakdown=False)

        assert repo.last_fixtures_call["competition_name"] == "Champions"

    @pytest.mark.anyio
    async def test_breakdown_assembles_correctly(self):
        fixture = _make_fixture(fixture_id=101)
        breakdown_map = {101: {"goal": FixtureActionBreakdown(count=2, pts=641.0)}}
        repo = FakePlayerEventRepository(fixtures=[fixture], breakdown_map=breakdown_map)
        uc = GetPlayerFixturesUseCase(repo)

        result = await uc.execute(player_id=1, include_breakdown=True)

        assert result[0].breakdown["goal"].count == 2
        assert result[0].breakdown["goal"].pts == 641.0

    @pytest.mark.anyio
    async def test_fixture_without_breakdown_entry_gets_none(self):
        fixture = _make_fixture(fixture_id=101)
        repo = FakePlayerEventRepository(fixtures=[fixture], breakdown_map={})
        uc = GetPlayerFixturesUseCase(repo)

        result = await uc.execute(player_id=1, include_breakdown=True)

        assert result[0].breakdown is None

    def test_fake_satisfies_protocol(self):
        repo = FakePlayerEventRepository()
        assert isinstance(repo, PlayerEventRepositoryProtocol)
