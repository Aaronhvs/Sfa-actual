import hashlib

import pytest

from sfa.domain.player_positions.ports import PositionAuditSnapshotSource
from sfa.infrastructure.repositories.position_audit_snapshot_source import FilePositionAuditSnapshotSource


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_loads_a_snapshot_without_changing_bytes_and_handles_powershell_utf8_bom(tmp_path):
    path = tmp_path / "snapshot.json"
    raw = b'\xef\xbb\xbf{"schema":"example"}'
    path.write_bytes(raw)
    source = FilePositionAuditSnapshotSource(path)
    assert isinstance(source, PositionAuditSnapshotSource)
    snapshot = await source.load()
    assert snapshot.content == '{"schema":"example"}'
    assert snapshot.sha256 == hashlib.sha256(raw).hexdigest()
    assert path.read_bytes() == raw


@pytest.mark.anyio
async def test_missing_snapshot_fails_instead_of_fetching_external_data(tmp_path):
    with pytest.raises(FileNotFoundError):
        await FilePositionAuditSnapshotSource(tmp_path / "missing.json").load()
