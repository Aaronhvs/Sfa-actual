from dataclasses import replace

import pytest

from sfa.domain.player_positions.ports import LineupEvidenceArchive, LineupEvidenceResponse
from sfa.infrastructure.providers.ssh_lineup_evidence_provider import SshLineupEvidenceProvider
from sfa.infrastructure.repositories.file_lineup_evidence_archive import FileLineupEvidenceArchive


@pytest.fixture
def anyio_backend():
    return "asyncio"


def response(fixture_id=1):
    return LineupEvidenceResponse(fixture_id, 200, '{\r\n"response":[]\r\n}', "2026-10-18T12:00:00+00:00",
                                 1000, 100, 300)


@pytest.mark.anyio
async def test_local_archive_preserves_raw_bytes_hashes_checkpoints_and_original(tmp_path):
    archive = FileLineupEvidenceArchive(tmp_path)
    assert isinstance(archive, LineupEvidenceArchive)
    assert await archive.load_manifest() is None and await archive.load_response(1) is None
    payload = response()
    digest = await archive.save_response(payload)
    assert await archive.load_response(1) == payload
    assert (tmp_path / "payloads" / f"1-{digest}.json").read_bytes() == payload.body.encode()
    assert await archive.save_response(payload) == digest
    assert len(list((tmp_path / "payloads").iterdir())) == 1
    content = '{"http_cap":11,"daily_reserve":100,"requests":[]}'
    await archive.save_manifest(content)
    assert await archive.load_manifest() == content
    assert (tmp_path / "requests.jsonl").exists() and (tmp_path / "quota-summary.json").exists()
    await archive.save_snapshot('{"read_only":true}')
    assert (tmp_path / "recovered-snapshot.json").read_text() == '{"read_only":true}'
    assert not list(tmp_path.rglob(".pending-*"))


@pytest.mark.anyio
async def test_tampered_payload_is_rejected_without_network_fallback(tmp_path):
    archive = FileLineupEvidenceArchive(tmp_path)
    digest = await archive.save_response(response())
    (tmp_path / "payloads" / f"1-{digest}.json").write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        await archive.load_response(1)


@pytest.mark.anyio
async def test_contradictory_versions_are_preserved_and_not_silently_selected(tmp_path):
    archive = FileLineupEvidenceArchive(tmp_path)
    first = response()
    await archive.save_response(first)
    with pytest.raises(ValueError, match="Contradictory"):
        await archive.save_response(replace(first, body='{"response":[1]}'))
    assert len(list((tmp_path / "payloads").iterdir())) == 2
    assert await archive.load_response(1) == first


@pytest.mark.anyio
async def test_quota_snapshots_can_change_while_fixture_evidence_stays_immutable(tmp_path):
    archive = FileLineupEvidenceArchive(tmp_path)
    await archive.save_response(response(None))
    await archive.save_response(replace(response(None), body='{"active":true}'))
    assert len(list((tmp_path / "payloads").iterdir())) == 2


@pytest.mark.anyio
async def test_exclusive_archive_lock_blocks_second_writer_and_is_released(tmp_path):
    first, second = FileLineupEvidenceArchive(tmp_path), FileLineupEvidenceArchive(tmp_path)
    await first.acquire()
    try:
        with pytest.raises(RuntimeError, match="already in use"):
            await second.acquire()
        with pytest.raises(RuntimeError, match="already in use"):
            await first.acquire()
    finally:
        await first.release()
    await second.acquire()
    await second.release()


@pytest.mark.parametrize("host", ["-oProxyCommand=bad", "host; bad", "host name", "user@host"])
def test_ssh_adapter_accepts_only_configured_host_aliases(host):
    with pytest.raises(ValueError, match="SSH host alias"):
        SshLineupEvidenceProvider(host)


def test_ssh_adapter_rejects_container_command_injection():
    with pytest.raises(ValueError, match="container"):
        SshLineupEvidenceProvider("sfa-vps", "container; bad")


@pytest.mark.anyio
async def test_invalid_fixture_identity_is_rejected_before_ssh():
    with pytest.raises(ValueError, match="fixture identity"):
        await SshLineupEvidenceProvider("sfa-vps").fetch_lineups(-1)
