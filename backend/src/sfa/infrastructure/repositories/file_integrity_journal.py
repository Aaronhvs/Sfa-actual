from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from sfa.domain.event_integrity_ports import IntegrityJournalPort


class FileIntegrityJournal(IntegrityJournalPort):
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    async def write(self, key: str, state: str, payload: str) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9-]+", key) or not re.fullmatch(r"[a-z]+", state):
            raise ValueError("Invalid journal key")
        target = self._directory / f"{key}-{state}.json"
        envelope = json.dumps({"sha256": hashlib.sha256(payload.encode()).hexdigest(), "payload": payload})
        if target.exists():
            if target.read_text(encoding="utf-8") != envelope:
                raise ValueError("Journal entry already exists with different content")
            return
        temporary = target.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(envelope)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
        if os.name != "nt":
            descriptor = os.open(self._directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
