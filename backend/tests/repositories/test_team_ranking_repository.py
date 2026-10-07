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
            "CREATE TABLE players (id INTEGER PRIMARY KEY, position TEXT, team_id INTEGER)",
            "CREATE TABLE player_stats (player_id INTEGER, fixture_id INTEGER, team_id INTEGER, "
            "season TEXT, minutes INTEGER)",
            "CREATE TABLE player_event_scores (player_id INTEGER, fixture_id INTEGER, season TEXT, "
            "rules_version_id INTEGER, action_type TEXT, final_points NUMERIC)",
        )
        for definition in definitions:
            connection.exec_driver_sql(definition)
        connection.exec_driver_sql("INSERT INTO competitions VALUES (3, 'club'), (350, 'national')")
        connection.exec_driver_sql("INSERT INTO players VALUES (1, 'DEL', 999), (2, 'MC', 999), (3, 'DEL', 999)")
        connection.exec_driver_sql("INSERT INTO team_strengths VALUES (3, 3, '2026')")
        fixtures = [(i, 3, "2026", 1, 2, f"2026-09-{i:02d} 12:00:00", "FT") for i in range(1, 13)]
        fixtures.extend([
            (20, 3, "2025", 1, 2, "2025-09-01 12:00:00", "FT"),
            (98, 3, "2026", 1, 2, "2026-09-29 12:00:00", "LIVE"),
            (99, 3, "2026", 1, 2, "2099-09-29 12:00:00", "FT"),
            (100, 350, "2026", 1, 2, "2026-09-29 12:00:00", "FT"),
        ])
        connection.exec_driver_sql("INSERT INTO fixtures VALUES (?, ?, ?, ?, ?, ?, ?)", fixtures)
        stats = [(1, i, 1, "2026", 90) for i in range(1, 13)]
        stats.extend([(1, 20, 1, "2025", 45), (1, 98, 1, "2026", 90), (1, 99, 1, "2026", 90),
                      (1, 100, 1, "2026", 90), (2, 12, None, "2026", 90), (2, 12, 3, "2026", 90),
                      (2, 11, 2, "2025", 90), (2, 10, 2, "2026", 0), (3, 12, 2, "2026", 90)])
        connection.exec_driver_sql("INSERT INTO player_stats VALUES (?, ?, ?, ?, ?)", stats)
        scores = [(1, 12, "2026", 3, "stats", 60), (1, 12, "2026", 3, "goal", 40),
                  (1, 12, "2026", 4, "stats", 9999), (1, 11, "2026", 3, "stats", 0),
                  (1, 11, "2026", 3, "yellow_card", -5), (1, 10, "2026", 3, "goal", 9999),
                  (1, 20, "2025", 3, "stats", 20), (1, 1, "2026", 3, "stats", 9999)]
        connection.exec_driver_sql("INSERT INTO player_event_scores VALUES (?, ?, ?, ?, ?, ?)", scores)
        rows = connection.execute(_players_statement(appearances(), 3)).mappings().all()
        keyed = {(r["team_id"], r["player_id"], r["season"]): r for r in rows}
        assert len(keyed) == 3
        current = keyed[1, 1, "2026"]
        assert current["observed_appearances"] == 10
        assert current["scored_appearances"] == 2
        assert current["scored_minutes"] == 180  # goal row must not duplicate appearance minutes
        assert current["individual_points"] == 95
        assert current["data_cutoff"].day == 12
        assert keyed[1, 1, "2025"]["individual_points"] == 20
        assert keyed[2, 3, "2026"]["individual_points"] is None
        assert keyed[2, 3, "2026"]["scored_minutes"] == 0
    engine.dispose()


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
                  scored_appearances=2, scored_minutes=180, individual_points=Decimal("95.50"), data_cutoff=AS_OF),
             dict(team_id=2, player_id=2, season="2026", position="MC", observed_appearances=1,
                  scored_appearances=0, scored_minutes=0, individual_points=None, data_cutoff=None)],
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
