from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql

from sfa.domain.team_ranking_ports import TeamRankingRepositoryProtocol
from sfa.infrastructure.repositories.team_ranking_repository import (
    TeamRankingRepository,
    _players_statement,
    _population,
    _primary_domestic_leagues,
    _recent_appearances,
    _recent_results_statement,
    _teams_statement,
    _version_statement,
)

AS_OF = datetime(2026, 9, 30, tzinfo=timezone.utc)


def sql(statement):
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).lower()


def appearances():
    return _recent_appearances("2026", "2025", "club", AS_OF, 10)


def test_query_contract_has_verified_sides_time_window_and_no_collective_scores():
    query = sql(_players_statement(appearances(), 3))
    assert "row_number() over (partition by fixture_sides.team_id, fixture_sides.season" in query
    assert "ordered_fixtures.recency <= 10" in query
    assert "fixtures.played_at <=" in query
    assert "'ft', 'aet', 'pen'" in query
    assert "ordered_fixtures.team_id = player_stats.team_id" in query
    assert "player_stats.season = ordered_fixtures.season" in query
    assert "player_stats.minutes > 0" in query
    assert "player_event_scores.rules_version_id = 3" in query
    assert "sum(player_event_scores.final_points)" in query
    assert "group by player_event_scores.player_id, player_event_scores.fixture_id" in query
    assert "left outer join individual_scores" in query
    assert "sfa_season_scores" not in query
    assert "achievement" not in query
    assert "players.team_id" not in query
    assert "player_event_scores.base_points" not in query
    assert "player_event_scores.m1" not in query
    assert "individual_scores.has_stats = 1" in query
    assert "verified_appearances as materialized" in query
    assert "individual_scores as materialized" in query
    assert "observed_seasons as materialized" in query
    assert "select distinct verified_appearances.season" in query


def test_version_selection_uses_distinct_covered_appearances_not_events():
    query = sql(_version_statement(appearances(), "2026"))
    assert "count(distinct (covered_versions.fixture_id, covered_versions.player_id))" in query
    assert "filter (where covered_versions.season = '2026') desc" in query
    assert "action_type = 'stats'" in query
    assert "scoring_rules_versions.is_active desc" in query
    assert "limit 1" in query
    assert "version_candidates as materialized" in query
    assert "intersect" in query
    assert "join scoring_rules_versions on true" in query


def test_population_only_requested_physical_season_and_kind():
    from sqlalchemy import select

    query = sql(select(_population("2026", "national")))
    assert "fixtures.season = '2026'" in query
    assert "team_strengths.season = '2026'" in query
    assert "participant_kind = 'national_team'" in query
    assert "2025" not in query


def test_real_aggregate_preserves_minutes_window_missing_coverage_and_historical_team():
    # Execute the portable appearance/aggregation SQL, without PostgreSQL or ORM mocks.
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        definitions = (
            "CREATE TABLE competitions (id INTEGER PRIMARY KEY, participant_kind TEXT)",
            "CREATE TABLE fixtures (id INTEGER PRIMARY KEY, competition_id INTEGER, season TEXT, "
            "home_team_id INTEGER, away_team_id INTEGER, played_at DATETIME, status TEXT)",
            "CREATE TABLE team_strengths (team_id INTEGER, competition_id INTEGER, season TEXT)",
            "CREATE TABLE players (id INTEGER PRIMARY KEY, position TEXT, team_id INTEGER, name TEXT, photo_url TEXT)",
            "CREATE TABLE player_stats (player_id INTEGER, fixture_id INTEGER, team_id INTEGER, "
            "season TEXT, minutes INTEGER)",
            "CREATE TABLE player_event_scores (player_id INTEGER, fixture_id INTEGER, season TEXT, "
            "rules_version_id INTEGER, action_type TEXT, final_points NUMERIC)",
        )
        for definition in definitions:
            connection.exec_driver_sql(definition)
        connection.exec_driver_sql("INSERT INTO competitions VALUES (3, 'club'), (350, 'national')")
        connection.exec_driver_sql("INSERT INTO players VALUES "
                                   "(1, 'DEL', 999, 'Transferred', 'photo'), (2, 'MC', 999, 'Two', NULL), "
                                   "(3, 'DEL', 999, 'Three', NULL)")
        connection.exec_driver_sql("INSERT INTO team_strengths VALUES (3, 3, '2026')")
        fixtures = [(i, 3, "2026", 1, 2, f"2026-09-{i:02d} 12:00:00", "FT") for i in range(1, 13)]
        fixtures.extend([
            (13, 3, "2026", 2, 3, "2026-09-13 12:00:00", "FT"),
            (20, 3, "2025", 1, 2, "2025-09-01 12:00:00", "FT"),
            (98, 3, "2026", 1, 2, "2026-09-29 12:00:00", "LIVE"),
            (99, 3, "2026", 1, 2, "2099-09-29 12:00:00", "FT"),
            (100, 350, "2026", 1, 2, "2026-09-29 12:00:00", "FT"),
        ])
        connection.exec_driver_sql("INSERT INTO fixtures VALUES (?, ?, ?, ?, ?, ?, ?)", fixtures)
        stats = [(1, i, 1, "2026", 90) for i in range(1, 13)]
        stats.extend([(1, 20, 1, "2025", 45), (1, 98, 1, "2026", 90), (1, 99, 1, "2026", 90),
                      (1, 100, 1, "2026", 90), (2, 12, None, "2026", 90), (2, 12, 3, "2026", 90),
                      (2, 11, 2, "2025", 90), (2, 10, 2, "2026", 0), (3, 12, 2, "2026", 90),
                      (1, 13, 2, "2026", 90)])
        connection.exec_driver_sql("INSERT INTO player_stats VALUES (?, ?, ?, ?, ?)", stats)
        scores = [(1, 12, "2026", 3, "stats", 60), (1, 12, "2026", 3, "goal", 40),
                  (1, 12, "2026", 4, "stats", 9999), (1, 11, "2026", 3, "stats", 0),
                  (1, 11, "2026", 3, "yellow_card", -5), (1, 10, "2026", 3, "goal", 9999),
                  (1, 20, "2025", 3, "stats", 20), (1, 1, "2026", 3, "stats", 9999),
                  (1, 13, "2026", 3, "stats", 30)]
        connection.exec_driver_sql("INSERT INTO player_event_scores VALUES (?, ?, ?, ?, ?, ?)", scores)
        rows = connection.execute(_players_statement(appearances(), 3)).mappings().all()
        keyed = {(r["team_id"], r["player_id"], r["season"]): r for r in rows}
        assert len(keyed) == 4
        current = keyed[1, 1, "2026"]
        assert current["observed_appearances"] == 10
        assert current["scored_appearances"] == 2
        assert current["scored_minutes"] == 180  # goal row must not duplicate appearance minutes
        assert current["individual_points"] == 95
        assert current["data_cutoff"].day == 12
        assert current["name"] == "Transferred" and current["photo_url"] == "photo"
        assert keyed[1, 1, "2025"]["individual_points"] == 20
        assert keyed[2, 1, "2026"]["individual_points"] == 30
        assert keyed[2, 1, "2026"]["scored_appearances"] == 1
        assert keyed[2, 3, "2026"]["individual_points"] is None
        assert keyed[2, 3, "2026"]["scored_minutes"] == 0
    engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize(("status", "gf", "ga", "outcome"), [
    ("FT", 0, 0, "D"), ("FT", 0, 1, "L"), ("FT", 1, 0, "W"),
    ("AET", 3, 2, "W"), ("AET", 2, 3, "L"), ("AET", 2, 2, "D"),
    ("PEN", 0, 0, None), ("PEN", 2, 2, None), ("PEN", 2, 1, "W"), ("PEN", 1, 2, "L"),
    ("FT", None, 0, None), ("AET", 0, None, None), ("PEN", None, None, None),
])
async def test_result_mapping_handles_actual_zero_missing_and_penalty_scores(status, gf, ga, outcome):
    session = FakeReadSession()
    session.results = [[dict(team_id=1, fixture_external_id=123, played_at=AS_OF, opponent_name="Opponent",
                             opponent_external_id=42, is_home=True, goals_for=gf, goals_against=ga, status=status)]]
    result = await TeamRankingRepository(session).get_recent_results((1,), "2026", "club", AS_OF)
    assert result[1][0].outcome == outcome
    assert (result[1][0].goals_for, result[1][0].goals_against) == (gf, ga)
    assert len(session.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("count", [2, 50])
async def test_page_form_adapter_uses_one_query_independent_of_team_count(count):
    session = FakeReadSession()
    session.results = [[dict(team_id=i, fixture_external_id=1000 + i, played_at=AS_OF,
                             opponent_name="Opponent", opponent_external_id=None, is_home=True,
                             goals_for=1, goals_against=0, status="FT") for i in range(1, count + 1)]]
    result = await TeamRankingRepository(session).get_recent_results(tuple(range(1, count + 1)), "2026", "club", AS_OF)
    assert len(result) == count and all(len(matches) == 1 for matches in result.values())
    assert len(session.calls) == 1


class FakeMappingsResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeReadSession:
    def __init__(self, teams=2):
        self.calls = []
        self.results = [
            [dict(id=i, name=f"Team {i}", external_id=None, competition_id=3,
                  competition="Premier League", competition_ids=[9, 3]) for i in range(1, teams + 1)],
            [dict(team_id=1, season="2025", elo_raw=Decimal("1800.20"), source="elo_v1", selection=1)],
            [dict(team_id=1, player_id=1, season="2025", position="DEL", observed_appearances=10,
                  scored_appearances=2, scored_minutes=180, individual_points=Decimal("95.50"), data_cutoff=AS_OF,
                  name="Player", photo_url="photo"),
             dict(team_id=2, player_id=2, season="2026", position="MC", observed_appearances=1,
                  scored_appearances=0, scored_minutes=0, individual_points=None, data_cutoff=None,
                  name="Unscored", photo_url=None)],
        ]

    async def execute(self, statement):
        self.calls.append(sql(statement))
        return FakeMappingsResult(self.results.pop(0))

    async def scalar(self, statement):
        self.calls.append(sql(statement))
        return "2026" if "order by fixtures.season desc" in self.calls[-1] else 3


@pytest.mark.anyio
async def test_adapter_maps_frozen_dtos_and_uses_four_queries_not_n_plus_one():
    for count in (2, 40):
        session = FakeReadSession(teams=count)
        repository = TeamRankingRepository(session)
        assert isinstance(repository, TeamRankingRepositoryProtocol)
        result = await repository.get_ranking_data("2026", "2025", "club", AS_OF, 10)
        assert len(session.calls) == 4
        assert len(result.teams) == count
        assert result.teams[0].competition_ids == (3, 9)
        assert result.elos[0].elo_raw == 1800.2
        assert result.players[0].individual_points == 95.5
        assert result.players[0].name == "Player" and result.players[0].photo_url == "photo"
        assert result.players[1].individual_points is None
        assert result.rules_version_id == 3
        elo_sql = session.calls[1]
        assert "row_number() over" in elo_sql
        assert "order by team_strengths.competition_id asc" in elo_sql
        assert "max(team_strengths.elo_raw)" not in elo_sql
        assert "team_strengths.source in" in elo_sql


@pytest.mark.anyio
async def test_adapter_empty_short_circuits_and_latest_kind_is_filtered():
    session = FakeReadSession(teams=0)
    repository = TeamRankingRepository(session)
    result = await repository.get_ranking_data("2026", "2025", "club", AS_OF, 10)
    assert not result.teams and len(session.calls) == 1
    assert await repository.latest_season("national") == "2026"
    assert "competitions.participant_kind = 'national_team'" in session.calls[-1]


def test_domestic_display_uses_fixture_participation_without_changing_population_memberships():
    query = sql(_teams_statement("2026", "club"))
    assert "fixtures.season = '2026'" in query
    assert "competitions.name in ('la liga', 'premier league', 'bundesliga', 'serie a', 'ligue 1')" in query
    assert "coalesce(primary_domestic_leagues.competition_id, teams.competition_id)" in query
    assert "coalesce(primary_domestic_leagues.name, competitions_1.name)" in query
    assert "array_agg(distinct(population.competition_id))" in query


def test_domestic_league_selection_executes_for_cup_catalogs_prior_seasons_and_multiple_leagues():
    from sqlalchemy import select

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE competitions (id INTEGER PRIMARY KEY, name TEXT, participant_kind TEXT)",
        )
        connection.exec_driver_sql("CREATE TABLE fixtures (id INTEGER PRIMARY KEY, competition_id INTEGER, "
                                   "season TEXT, home_team_id INTEGER, away_team_id INTEGER, played_at DATETIME)")
        connection.exec_driver_sql("INSERT INTO competitions VALUES "
                                   "(1,'La Liga','club'),(3,'Premier League','club'),(9,'Ligue 1','club'),"
                                   "(10,'Champions League','club'),(22,'Copa del Rey','club'),"
                                   "(350,'World Cup','national_team')")
        fixtures = [(1, 22, "2026", 1, 101, "2026-08-01"),  # Barcelona's cup must not be primary
                    (2, 1, "2026", 1, 101, "2026-08-02"),
                    (3, 3, "2026", 2, 102, "2026-08-01"),  # Liverpool
                    (4, 9, "2026", 3, 103, "2026-08-01"),  # PSG
                    (5, 10, "2026", 4, 104, "2026-08-01"),  # no domestic league evidence
                    (6, 1, "2025", 4, 104, "2025-08-01"),  # must not use old association
                    (7, 3, "2026", 5, 105, "2026-08-01"),
                    (8, 3, "2026", 5, 105, "2026-08-02"),
                    (9, 9, "2026", 5, 105, "2026-08-03"),  # most fixtures wins over newest
                    (10, 350, "2026", 6, 106, "2026-08-01")]
        connection.exec_driver_sql("INSERT INTO fixtures VALUES (?, ?, ?, ?, ?, ?)", fixtures)
        primary = _primary_domestic_leagues("2026", "club")
        rows = connection.execute(select(primary).where(primary.c.preference == 1)).mappings().all()
        selected = {r["team_id"]: (r["competition_id"], r["name"]) for r in rows}
        assert selected[1] == (1, "La Liga")
        assert selected[2] == (3, "Premier League")
        assert selected[3] == (9, "Ligue 1")
        assert selected[5] == (3, "Premier League")
        assert 4 not in selected and 6 not in selected
    engine.dispose()


def test_both_national_aliases_compile_to_stored_kind_for_population_and_appearances():
    from sqlalchemy import select

    for alias in ("national", "national_team"):
        for statement in (select(_population("2026", alias)),
                          select(_recent_appearances("2026", "2025", alias, AS_OF, 10))):
            assert "competitions.participant_kind = 'national_team'" in sql(statement)


def test_recent_results_query_is_page_bounded_and_filters_before_window():
    query = sql(_recent_results_statement((1, 2), "2026", "national", AS_OF))
    assert "fixtures.home_team_id in (1, 2)" in query
    assert "fixtures.away_team_id in (1, 2)" in query
    assert "fixtures.season = '2026'" in query and "2025" not in query
    assert "competitions.participant_kind = 'national_team'" in query
    assert "fixtures.status in ('ft', 'aet', 'pen')" in query
    assert "fixtures.played_at <=" in query
    assert "partition by recent_result_sides.team_id" in query
    assert "ordered_results.recency <= 5" in query
    assert "order by ordered_results.team_id, ordered_results.played_at, ordered_results.fixture_id" in query
    assert "player_stats" not in query  # actual results do not depend on scored appearances


@pytest.mark.anyio
async def test_recent_results_execute_last_five_missing_scores_penalties_home_away_and_exclusions():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE competitions (id INTEGER PRIMARY KEY, participant_kind TEXT)")
        connection.exec_driver_sql("CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT, external_id INTEGER)")
        connection.exec_driver_sql(
            "CREATE TABLE fixtures (id INTEGER PRIMARY KEY, external_id INTEGER, competition_id INTEGER, "
            "season TEXT, home_team_id INTEGER, away_team_id INTEGER, played_at DATETIME, status TEXT, "
            "home_goals INTEGER, away_goals INTEGER)",
        )
        connection.exec_driver_sql("INSERT INTO competitions VALUES (3, 'club'), (350, 'national_team')")
        connection.exec_driver_sql("INSERT INTO teams VALUES (1, 'One', 101), (2, 'Two', NULL), (3, 'Three', 103)")
        fixtures = [
            (1, 1001, 3, "2026", 1, 2, "2026-09-01 12:00:00", "FT", 9, 0),
            (2, 1002, 3, "2026", 1, 2, "2026-09-02 12:00:00", "FT", 3, 1),
            (3, 1003, 3, "2026", 2, 1, "2026-09-03 12:00:00", "AET", 1, 1),
            (4, 1004, 3, "2026", 1, 2, "2026-09-04 12:00:00", "FT", None, 2),
            (5, 1005, 3, "2026", 1, 2, "2026-09-05 12:00:00", "PEN", 2, 2),
            (6, 1006, 3, "2026", 2, 1, "2026-09-05 12:00:00", "FT", 2, 0),
            (7, 1007, 3, "2025", 1, 2, "2026-09-29 12:00:00", "FT", 9, 0),
            (8, 1008, 3, "2026", 1, 2, "2026-10-01 12:00:00", "FT", 9, 0),
            (9, 1009, 3, "2026", 1, 2, "2026-09-29 12:00:00", "LIVE", 9, 0),
            (10, 1010, 350, "2026", 1, 2, "2026-09-29 12:00:00", "FT", 9, 0),
            (11, 1011, 3, "2026", 1, 2, "2026-09-29 12:00:00", "NS", None, None),
            (12, 1012, 3, "2026", 3, 2, "2026-09-06 12:00:00", "PEN", 1, 0),
        ]
        connection.exec_driver_sql("INSERT INTO fixtures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", fixtures)

        class ExecutedReadSession:
            def __init__(self):
                self.calls = []

            async def execute(self, statement):
                self.calls.append(statement)
                return FakeMappingsResult(connection.execute(statement).mappings().all())

        session = ExecutedReadSession()
        repo = TeamRankingRepository(session)
        results = await repo.get_recent_results((1, 3, 999), "2026", "club", AS_OF)
        assert len(session.calls) == 1
        matches = results[1]
        assert [m.fixture_external_id for m in matches] == [1002, 1003, 1004, 1005, 1006]
        assert [m.outcome for m in matches] == ["W", "D", None, None, "L"]
        assert [m.is_home for m in matches] == [True, False, True, True, False]
        assert (matches[-1].goals_for, matches[-1].goals_against) == (0, 2)
        assert matches[2].goals_for is None and matches[2].goals_against == 2
        assert all(m.opponent_name == "Two" and m.opponent_logo_url is None for m in matches)
        assert results[3][0].outcome == "W" and results[3][0].status == "PEN"
        assert results[999] == ()
        reverse = (await repo.get_recent_results((2,), "2026", "club", AS_OF))[2]
        assert reverse[-1].opponent_logo_url == "https://media.api-sports.io/football/teams/103.png"
        assert reverse[-1].outcome == "L"
        assert await repo.get_recent_results((), "2026", "club", AS_OF) == {}
        assert len(session.calls) == 2
        with pytest.raises(ValueError, match="50"):
            await repo.get_recent_results(tuple(range(51)), "2026", "club", AS_OF)
        assert len(session.calls) == 2
    engine.dispose()
