from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from sfa.application.use_cases.get_latest_tournament_mvps import GetLatestTournamentMvpsUseCase
from sfa.application.use_cases.get_tournament_mvps import GetTournamentMvpsUseCase
from sfa.domain.matchday_mvp import (
    FEATURED_NAMES,
    MatchdayMvpCacheProtocol,
    MatchdayMvpRepositoryProtocol,
    MvpPerformance,
    TournamentMvpReaderProtocol,
)
from sfa.domain.player_leads.ports import ScopeRulesVersionResolverProtocol
from sfa.domain.ports import (
    SeasonDTO,
    SeasonRepositoryProtocol,
    TournamentCompetitionDTO,
    TournamentFixtureDTO,
    TournamentRepositoryProtocol,
    TournamentTeamDTO,
)
from sfa.domain.season_scope import AwardPeriodScope, InconsistentScopeRulesVersionError, ScopeKind, ScoreSource

SCOPE = AwardPeriodScope("season-2026", "2026/2027", ScopeKind.AWARD_PERIOD,
                         (ScoreSource("2026", tuple(range(1, 10))),), is_latest=True)
COMP = TournamentCompetitionDTO(1, "La Liga", "ES", "2026", "club", 3, 2, 1)
FIXTURE = TournamentFixtureDTO(1, 1234, 1, "regular", 1, datetime(2026, 10, 26, tzinfo=timezone.utc),
                               "FT", 1, 0, TournamentTeamDTO(1, 529, "Barcelona"),
                               TournamentTeamDTO(2, 541, "Real Madrid"))


class FakeRepository(MatchdayMvpRepositoryProtocol):
    def __init__(self):
        self.exists, self.loads, self.stamp, self.change_during_read = True, 0, "a", False

    async def competition_exists(self, competition_id):
        return self.exists

    async def get_fixtures(self, competition_id, season):
        self.loads += 1
        return [FIXTURE]

    async def get_performances(self, competition_id, season, rules_version_id):
        if self.change_during_read:
            self.stamp = "changed"
        return [MvpPerformance(1, 1, "Player", None, 1, Decimal("1234.56"), 1, 0)]

    async def get_positions(self, scope, competition_id):
        return {1: "MC"}

    async def get_data_stamp(self, scope, competition_id, season, rules_version_id):
        return self.stamp


class FakeTournaments(TournamentRepositoryProtocol):
    def __init__(self, competitions=(COMP,)):
        self.competitions = competitions

    async def resolve_latest_season(self):
        return "2026"

    async def list_competitions(self, season):
        return list(self.competitions) if season == "2026" else []

    async def get_tournament(self, competition_id, season):
        return None

    async def list_fixture_dates(self, season):
        return []

    async def get_fixture_groups(self, season, fixture_date):
        return []

    async def get_fixture_by_external_id(self, fixture_external_id, season):
        return None


class FakeSeasons(SeasonRepositoryProtocol):
    async def get_available_seasons(self):
        return [SeasonDTO("2026", True, False, "season-2026", "2026/2027", "award_period", False)]

    async def resolve_scope(self, scope_key=None):
        return SCOPE

    async def get_available_scopes_for_player(self, player_id):
        return await self.get_available_seasons()


class FakeRules(ScopeRulesVersionResolverProtocol):
    def __init__(self):
        self.calls, self.inconsistent = [], False

    async def resolve_rules_version_id_for_scope(self, scope, preferred_rules_version_id=None):
        self.calls.append((scope, preferred_rules_version_id))
        if self.inconsistent:
            raise InconsistentScopeRulesVersionError(scope.key)
        return preferred_rules_version_id or 7


class FakeCache(MatchdayMvpCacheProtocol):
    def __init__(self):
        self.data = {}

    async def read(self, key):
        return self.data.get(key)

    async def write(self, key, items):
        self.data[key] = items


def make_use_case(repository=None, tournaments=None, rules=None, cache=None):
    return GetTournamentMvpsUseCase(repository or FakeRepository(), tournaments or FakeTournaments(),
                                    FakeSeasons(), rules or FakeRules(), cache or FakeCache(), 4)


@pytest.mark.anyio
async def test_full_protocol_fakes_and_happy_path_with_active_rules_and_cache():
    repo, rules, cache = FakeRepository(), FakeRules(), FakeCache()
    for fake, port in [(repo, MatchdayMvpRepositoryProtocol), (rules, ScopeRulesVersionResolverProtocol),
                       (cache, MatchdayMvpCacheProtocol), (FakeSeasons(), SeasonRepositoryProtocol),
                       (FakeTournaments(), TournamentRepositoryProtocol)]:
        assert isinstance(fake, port)
    use_case = make_use_case(repo, rules=rules, cache=cache)
    assert isinstance(use_case, TournamentMvpReaderProtocol)
    first = await use_case.execute(1)
    second = await use_case.execute(1, "2026")
    assert first == second and first.items[0].sfa_pts == 1234.56 and first.items[0].player.position == "MC"
    assert repo.loads == 1 and rules.calls == [(SCOPE, 4)]
    repo.stamp = "recalculated"
    await use_case.execute(1)
    assert repo.loads == 2


@pytest.mark.anyio
async def test_missing_season_and_missing_competition_and_inconsistent_versions():
    repo, rules = FakeRepository(), FakeRules()
    use_case = make_use_case(repo, rules=rules)
    assert (await use_case.execute(1, "1900")).items == ()
    repo.exists = False
    with pytest.raises(ValueError, match="Competition not found"):
        await use_case.execute(999)
    repo.exists, rules.inconsistent = True, True
    with pytest.raises(InconsistentScopeRulesVersionError):
        await use_case.execute(1)


@pytest.mark.anyio
async def test_does_not_cache_snapshot_that_changed_while_loading():
    repo, cache = FakeRepository(), FakeCache()
    repo.change_during_read = True
    assert (await make_use_case(repo, cache=cache).execute(1)).items
    assert cache.data == {}


@pytest.mark.anyio
async def test_latest_all_eight_in_priority_order_and_empty_data():
    competitions = [replace(COMP, id=i + 1, name=name.title()) for i, name in enumerate(FEATURED_NAMES)]
    competitions += [replace(COMP, id=9, name="FA Cup"), replace(COMP, id=10, completed_fixtures=0)]
    tournaments = FakeTournaments(tuple(reversed(competitions)))
    sample, = (await make_use_case().execute(1)).items

    class FakeReader(TournamentMvpReaderProtocol):
        async def get_items(self, competition, season):
            return (sample, replace(sample, round_key="matchday-2", matchday=2, complete=False, pending_fixtures=1))

    reader = FakeReader()
    result = await GetLatestTournamentMvpsUseCase(tournaments, reader).execute()
    assert [entry.competition.id for entry in result.items] == list(range(1, 9))
    assert all(entry.mvp.matchday == 2 and not entry.mvp.complete for entry in result.items)
    assert (await GetLatestTournamentMvpsUseCase(tournaments, reader).execute("1900")).items == ()
