from __future__ import annotations

import json
from dataclasses import asdict
from uuid import uuid4

from sfa.domain.event_integrity_ports import IntegrityJournalPort
from sfa.domain.title_correction import (
    CalculateTitleBonusesPort,
    InferTitleChampionsPort,
    InferTitleKnockoutPort,
    RefreshTitleHonorsPort,
    TitleCorrectionPlan,
    TitleCorrectionRepositoryPort,
    TitleCorrectionSnapshot,
    fingerprint,
    validate_evidence,
)
from sfa.domain.trophy_results import INTERCONTINENTAL_POLICY


class ApplyCompetitionTitleCorrectionUseCase:
    def __init__(
        self, repository: TitleCorrectionRepositoryPort, journal: IntegrityJournalPort,
        champions: InferTitleChampionsPort, knockout: InferTitleKnockoutPort,
        bonuses: CalculateTitleBonusesPort, honors: RefreshTitleHonorsPort,
    ) -> None:
        self._repository, self._journal = repository, journal
        self._champions, self._knockout = champions, knockout
        self._bonuses, self._honors = bonuses, honors

    async def execute(self, plan: TitleCorrectionPlan) -> tuple[str, TitleCorrectionSnapshot]:
        if (fingerprint(validate_evidence(plan.evidence)) != plan.source_hash
                or plan.policy_version != INTERCONTINENTAL_POLICY):
            raise ValueError("Correction evidence or policy changed")
        await self._repository.lock()
        current = await self._repository.snapshot(plan.evidence)
        if current.fingerprint != plan.before.fingerprint:
            raise ValueError("Correction snapshot changed; prepare again")
        key = "psg-titles-2025-" + uuid4().hex
        await self._journal.write(key, "intent", json.dumps(asdict(plan), sort_keys=True))
        await self._repository.allow_publication(True)
        competition_ids = await self._repository.import_evidence(plan.evidence)
        await self._champions.execute(season="2025", rules_version_id=4, competition_id=competition_ids[0])
        for competition_id in competition_ids[1:]:
            await self._knockout.execute(competition_id=competition_id, season="2025", rules_version_id=4)
        for competition_id in competition_ids:
            result = await self._bonuses.execute(season="2025", competition_id=competition_id, rules_version_id=4)
            if result.status != "completed":
                raise ValueError("Title bonus calculation failed")
        await self._honors.execute(scope_key="season-2025", rules_version_id=4)
        await self._repository.allow_publication(False)
        after = await self._repository.verify(plan.before, plan.evidence)
        await self._journal.write(key, "prepared", json.dumps(asdict(after), sort_keys=True))
        return key, after

    async def revert(
        self, before: TitleCorrectionSnapshot, after: TitleCorrectionSnapshot, evidence: str,
    ) -> str:
        validate_evidence(evidence)
        await self._repository.lock()
        if (await self._repository.snapshot(evidence)).fingerprint != after.fingerprint:
            raise ValueError("Correction revert CAS failed; newer activity exists")
        key = "psg-titles-revert-" + uuid4().hex
        await self._journal.write(key, "intent", json.dumps(asdict(before), sort_keys=True))
        await self._repository.allow_publication(True)
        await self._repository.restore(before, after, evidence)
        await self._repository.allow_publication(False)
        if (await self._repository.snapshot(evidence)).fingerprint != before.fingerprint:
            raise ValueError("Correction revert did not restore exact before state")
        await self._journal.write(key, "prepared", json.dumps(asdict(before), sort_keys=True))
        return key
