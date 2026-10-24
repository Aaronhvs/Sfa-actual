import logging

import pytest

from sfa.application.use_cases.get_player_leads import GetPlayerLeadsUseCase
from sfa.domain.player_leads import (
    LeadMetric,
    LeadSample,
    PlayerLeadsCacheProtocol,
    PlayerLeadsCalculator,
    PlayerLeadsRepositoryProtocol,
    ScopeRulesVersionResolverProtocol,
)
from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol
from sfa.domain.season_scope import (
    AwardPeriodScope,
    InconsistentScopeRulesVersionError,
    ScopeKind,
    ScopeNotFoundError,
    ScoreSource,
)

SCOPE = AwardPeriodScope("season-2025", "2025/26", ScopeKind.AWARD_PERIOD, (ScoreSource("2025", (140,)),),
                         is_latest=True)
ALL_TIME = AwardPeriodScope("all", "Histórico", ScopeKind.ALL_TIME, ())


def _samples():
    star = LeadSample(1, "2025", 140, "La Liga", "club", "EXT", minutes=900, goals=20, np_goals=20,
                      np_shots_on=25, assists=8, passes_key=40)
    filler = [LeadSample(index, "2025", 140, "La Liga", "club", "EXT", minutes=900, goals=3, np_goals=3,
                         np_shots_on=12) for index in range(100, 112)]
    return [star, *filler]


class FakeSeasonRepository(SeasonRepositoryProtocol):
    def __init__(self, scope=SCOPE):
        self.scope = scope

    async def get_available_seasons(self) -> list[SeasonDTO]:
        return []

    async def resolve_scope(self, scope_key=None):
        if scope_key == "season-1900":
            raise ScopeNotFoundError(scope_key)
        return self.scope

    async def get_available_scopes_for_player(self, player_id: int) -> list[SeasonDTO]:
        return []


class FakeRulesResolver(ScopeRulesVersionResolverProtocol):
    def __init__(self, version=7, inconsistent=False):
        self.version, self.inconsistent = version, inconsistent

    async def resolve_rules_version_id_for_scope(self, scope, preferred_rules_version_id=None):
        if self.inconsistent:
            raise InconsistentScopeRulesVersionError(scope.key)
        return self.version


class FakeLeadsRepository(PlayerLeadsRepositoryProtocol):
    def __init__(self, samples=None):
        self.samples = _samples() if samples is None else samples
        self.sample_calls = 0
        self.versions = []

    async def get_competition_samples(self, scope, rules_version_id):
        self.sample_calls += 1
        self.versions.append(rules_version_id)
        return self.samples

    async def get_scope_positions(self, scope):
        return {}

    async def get_data_stamp(self, scope, rules_version_id):
        return "stamp"


class FakeCache(PlayerLeadsCacheProtocol):
    def __init__(self, lock_available=True):
        self.snapshots = {}
        self.lock_available = lock_available
        self.released = []

    async def read_player(self, key, player_id):
        snapshot = self.snapshots.get(key)
        return None if snapshot is None else snapshot.for_player(player_id)

    async def save_snapshot(self, key, snapshot):
        self.snapshots[key] = snapshot

    async def acquire_lock(self, key):
        return "token" if self.lock_available else None

    async def release_lock(self, key, token):
        self.released.append((key, token))


def _use_case(*, season=None, rules=None, repo=None, cache=None):
    return GetPlayerLeadsUseCase(season or FakeSeasonRepository(), rules or FakeRulesResolver(),
                                 repo or FakeLeadsRepository(), cache or FakeCache(), PlayerLeadsCalculator())


class TestGetPlayerLeadsUseCase:
    @pytest.mark.anyio
    async def test_returns_podium_items_and_saves_snapshot(self):
        cache = FakeCache()
        result = await _use_case(cache=cache).execute(1)
        assert result.supported and result.scope_key == "season-2025" and result.rules_version_id == 7
        assert 0 < len(result.items) <= 3 and all(item.rank <= 3 for item in result.items)
        assert cache.snapshots and cache.released == [("leads-v2:season-2025:7:stamp", "token")]

    @pytest.mark.anyio
    async def test_cache_hit_skips_samples(self):
        repo, cache = FakeLeadsRepository(), FakeCache()
        use_case = _use_case(repo=repo, cache=cache)
        await use_case.execute(1)
        second = await use_case.execute(1)
        assert repo.sample_calls == 1 and second.items

    @pytest.mark.anyio
    async def test_miss_without_lock_answers_without_saving(self):
        cache = FakeCache(lock_available=False)
        result = await _use_case(cache=cache).execute(1)
        assert result.items and not cache.snapshots and not cache.released

    @pytest.mark.anyio
    async def test_all_scope_is_not_supported(self):
        repo = FakeLeadsRepository()
        result = await _use_case(repo=repo).execute(1, "all")
        assert not result.supported and result.items == () and repo.sample_calls == 0
        all_time = await _use_case(season=FakeSeasonRepository(ALL_TIME)).execute(1, "historic")
        assert not all_time.supported

    @pytest.mark.anyio
    async def test_no_latest_scope_is_empty_but_supported(self):
        result = await _use_case(season=FakeSeasonRepository(None)).execute(1)
        assert result.supported and result.items == () and result.scope_key is None

    @pytest.mark.anyio
    async def test_unknown_scope_propagates(self):
        with pytest.raises(ScopeNotFoundError):
            await _use_case().execute(1, "season-1900")

    @pytest.mark.anyio
    async def test_inconsistent_rules_drop_only_the_sfa_metric(self):
        repo = FakeLeadsRepository()
        result = await _use_case(rules=FakeRulesResolver(inconsistent=True), repo=repo).execute(1)
        assert result.rules_version_id is None and repo.versions == [None]
        assert result.items and all(item.metric != LeadMetric.BIG_GAME_POINTS_PER90 for item in result.items)

    @pytest.mark.anyio
    async def test_max_rank_and_limit_filter_without_reordering(self):
        full = await _use_case().execute(1)
        limited = await _use_case().execute(1, max_rank=1, limit=1)
        assert limited.items == full.items[:1] and limited.items[0].rank == 1

    @pytest.mark.anyio
    @pytest.mark.parametrize("max_rank,limit", [(0, 3), (4, 3), (3, 6)])
    async def test_out_of_range_request_raises(self, max_rank, limit):
        with pytest.raises(ValueError):
            await _use_case().execute(1, max_rank=max_rank, limit=limit)

    @pytest.mark.anyio
    async def test_player_without_leads_gets_empty_list(self):
        assert (await _use_case().execute(999)).items == ()

    @pytest.mark.anyio
    async def test_logs_hit_and_miss(self, caplog):
        use_case = _use_case()
        with caplog.at_level(logging.INFO):
            await use_case.execute(1)
            await use_case.execute(1)
        messages = " ".join(record.getMessage() for record in caplog.records)
        assert "[GetPlayerLeadsUseCase] Cache miss" in messages and "[GetPlayerLeadsUseCase] Cache hit" in messages
