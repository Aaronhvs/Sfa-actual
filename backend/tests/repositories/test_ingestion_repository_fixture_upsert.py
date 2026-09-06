from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository


class FakeResult:
    def scalar_one(self) -> int:
        return 17


class FakeSession:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult()

    async def flush(self) -> None:
        return None


@pytest.mark.anyio
async def test_fixture_upsert_refreshes_canonical_identity_and_schedule() -> None:
    session = FakeSession()
    played_at = datetime(2026, 8, 23, 18, 45, tzinfo=timezone.utc)

    fixture_id = await IngestionRepository(session).upsert_fixture(
        external_id=1552735,
        competition_id=9,
        home_team_id=110,
        away_team_id=99,
        stage="regular",
        season="2026",
        played_at=played_at,
        matchday=2,
        status="FT",
        home_goals=2,
        away_goals=2,
        score_source="api_football",
    )

    assert fixture_id == 17
    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    for column in (
        "competition_id",
        "home_team_id",
        "away_team_id",
        "season",
        "played_at",
        "stage",
        "status",
        "home_goals",
        "away_goals",
    ):
        assert f"{column} =" in sql
