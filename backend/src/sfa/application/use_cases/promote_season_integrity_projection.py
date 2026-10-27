from __future__ import annotations

import json
from dataclasses import asdict
from uuid import uuid4

from sfa.domain.event_integrity_ports import IntegrityJournalPort, SeasonIntegrityPublicationRepositoryPort


class PromoteSeasonIntegrityProjectionUseCase:
    """Publish a prepared projection atomically; the input adapter owns commit."""

    def __init__(self, repository: SeasonIntegrityPublicationRepositoryPort, journal: IntegrityJournalPort) -> None:
        self._repository = repository
        self._journal = journal

    async def execute(self, *, reverting: bool = False):
        await self._repository.lock()
        before = await self._repository.validate(reverting)
        key = f"season-2025-{'revert' if reverting else 'publish'}-{uuid4().hex}"
        await self._journal.write(key, "intent", json.dumps(asdict(before), sort_keys=True))
        after = await self._repository.replace(reverting)
        await self._journal.write(key, "prepared", json.dumps(asdict(after), sort_keys=True))
        return key, after


class RevertSeasonIntegrityProjectionUseCase(PromoteSeasonIntegrityProjectionUseCase):
    async def execute(self):
        return await super().execute(reverting=True)
