from __future__ import annotations

import json
from dataclasses import asdict
from uuid import uuid4

from sfa.domain.event_integrity import PARSER_VERSION, IntegrityPlan, normalize_context_plan
from sfa.domain.event_integrity_ports import IntegrityJournalPort, SeasonEventIntegrityRepositoryPort


class ApplySeasonEventIntegrityUseCase:
    def __init__(self, repository: SeasonEventIntegrityRepositoryPort, journal: IntegrityJournalPort) -> None:
        self._repository = repository
        self._journal = journal

    async def normalize_context(self, fixture_id: int) -> int:
        return await self.execute(normalize_context_plan(await self._repository.snapshot(fixture_id)))

    async def normalize_contexts(self) -> int:
        count = 0
        for fixture_id in await self._repository.get_context_conflict_fixture_ids():
            count += await self.normalize_context(fixture_id)
        return count

    async def execute(self, plan: IntegrityPlan) -> int:
        if plan.parser_version != PARSER_VERSION:
            raise ValueError("Integrity parser changed; prepare a new plan")
        if plan.pending:
            raise ValueError("Cannot apply a pending integrity plan")
        if not plan.changes and not plan.appearance_changes and plan.fixture_goals is None:
            return 0
        before = await self._repository.snapshot(plan.fixture_id)
        if before.fingerprint != plan.fingerprint:
            raise ValueError("Integrity snapshot changed; prepare a new plan")
        key = f"{plan.external_id}-{plan.source_hash}-{uuid4().hex}"
        await self._journal.write(
            key, "intent", json.dumps({"plan": asdict(plan), "before": asdict(before)}, sort_keys=True)
        )
        count = await self._repository.apply(plan)
        after = await self._repository.snapshot(plan.fixture_id)
        await self._journal.write(key, "prepared", json.dumps(asdict(after), sort_keys=True))
        return count
