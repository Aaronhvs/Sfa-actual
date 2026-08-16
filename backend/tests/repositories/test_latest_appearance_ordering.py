from sfa.infrastructure.repositories.enrich_position_repository import (
    EnrichPositionRepository,
)
from sfa.infrastructure.repositories.player_event_repository import PlayerEventRepository
from sfa.infrastructure.repositories.player_repository import PlayerRepository


class _EmptyMappingsResult:
    def mappings(self):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _EmptyMappingsResult()


async def test_player_repository_orders_latest_team_by_played_at() -> None:
    session = _RecordingSession()

    assert await PlayerRepository(session).get_by_id(7) is None

    sql = str(session.statements[0]).lower()
    assert "fixtures.played_at desc" in sql
    assert "fixtures.id desc" in sql
    assert "player_stats.id desc" in sql
    assert "player_stats.team_id = fixtures.home_team_id" in sql


async def test_enrichment_latest_team_uses_date_and_keeps_season_filter() -> None:
    session = _RecordingSession()

    rows = await EnrichPositionRepository(session).get_players_without_tm_source(
        limit=10,
        season="2026",
    )

    assert rows == []
    sql = str(session.statements[0]).lower()
    assert "fixtures.played_at desc" in sql
    assert "player_stats.season" in sql
    assert "player_stats.team_id = fixtures.away_team_id" in sql


async def test_fixture_history_never_uses_season_score_as_team_fallback() -> None:
    session = _RecordingSession()

    rows = await PlayerEventRepository(session).get_fixtures_by_player(
        player_id=7,
        season="2025",
        rules_version_id=4,
    )

    assert rows == []
    sql = str(session.statements[0]).lower()
    assert "sfa_season_scores" not in sql
    assert "player_stats.team_id = fixtures.home_team_id" in sql
    assert "player_events.team_id = fixtures.away_team_id" in sql
