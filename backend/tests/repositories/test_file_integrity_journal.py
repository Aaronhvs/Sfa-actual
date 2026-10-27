import json

import pytest

from sfa.infrastructure.repositories.file_integrity_journal import FileIntegrityJournal


@pytest.mark.anyio
async def test_journal_is_immutable_and_idempotent(tmp_path):
    journal = FileIntegrityJournal(tmp_path)
    await journal.write("123-hash", "intent", "before")
    await journal.write("123-hash", "intent", "before")
    row = json.loads((tmp_path / "123-hash-intent.json").read_text())
    assert row["payload"] == "before"
    with pytest.raises(ValueError, match="different content"):
        await journal.write("123-hash", "intent", "different")
    with pytest.raises(ValueError, match="Invalid journal"):
        await journal.write("../escape", "intent", "before")
