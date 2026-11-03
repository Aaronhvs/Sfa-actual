import pytest
from sqlalchemy.dialects import postgresql

from sfa.domain.ingestion_ports import MissingPlayerPositionError
from sfa.infrastructure.models.enums import Position
from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository


class FakeResult:
    def scalar_one(self):
        return 17


class FakeSession:
    def __init__(self, stored):
        self.stored = stored
        self.writes = []

    async def scalar(self, statement):
        return self.stored

    async def execute(self, statement):
        self.writes.append(statement)
        return FakeResult()

    async def flush(self):
        pass


@pytest.mark.anyio
async def test_unknown_new_identity_cannot_be_inserted_with_a_fabricated_position():
    session = FakeSession(None)
    with pytest.raises(MissingPlayerPositionError):
        await IngestionRepository(session).upsert_player(42, "Unknown", None)
    assert not session.writes


@pytest.mark.anyio
async def test_missing_provider_position_cannot_overwrite_existing_goalkeeper():
    session = FakeSession(Position.GK)
    assert await IngestionRepository(session).upsert_player(42, "Known keeper", None) == 17
    compiled = session.writes[0].compile(dialect=postgresql.dialect())
    assert compiled.params['position'] == Position.GK
    assert 'position =' not in str(compiled).split('DO UPDATE SET')[1]


class FakePositionSession:
    def __init__(self, available, position):
        self.values = iter([available, position])
        self.reads = []

    async def scalar(self, statement):
        self.reads.append(str(statement.compile(dialect=postgresql.dialect())))
        return next(self.values)


@pytest.mark.anyio
@pytest.mark.parametrize("available", [True, False])
async def test_missing_position_resolution_supports_databases_without_position_publication(available):
    session = FakePositionSession(available, Position.GK)
    result = await IngestionRepository(session).resolve_missing_player_position(17, 55, 9)
    assert result == Position.GK
    assert ("sfa_accepted_position(" in session.reads[1]) is available
