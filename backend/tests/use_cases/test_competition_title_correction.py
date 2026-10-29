from __future__ import annotations

from dataclasses import replace

import pytest

from sfa.application.use_cases.apply_competition_title_correction import ApplyCompetitionTitleCorrectionUseCase
from sfa.application.use_cases.prepare_competition_title_correction import PrepareCompetitionTitleCorrectionUseCase
from tests.title_correction_fakes import FakeTitleJournal, FakeTitleRepository, FakeTitleWorkflow, evidence


def workflow():
    calls = []
    repo, journal = FakeTitleRepository(calls), FakeTitleJournal(calls)
    bonuses = FakeTitleWorkflow("bonuses", calls)
    apply = ApplyCompetitionTitleCorrectionUseCase(
        repo, journal, FakeTitleWorkflow("champions", calls), FakeTitleWorkflow("knockout", calls),
        bonuses, FakeTitleWorkflow("honors", calls),
    )
    return PrepareCompetitionTitleCorrectionUseCase(repo), apply, repo, journal, bonuses, calls


@pytest.mark.anyio
async def test_apply_journals_before_guarded_write_and_closes_all_three_competitions():
    prepare, apply, repo, journal, _, calls = workflow()
    plan = await prepare.execute(evidence())
    key, after = await apply.execute(plan)
    assert calls.index(("journal", "intent")) < calls.index(("allow", True)) < calls.index("import")
    assert calls.index(("allow", False)) < calls.index("verify") < calls.index(("journal", "prepared"))
    assert [c[1]["competition_id"] for c in calls if isinstance(c, tuple) and c[0] == "bonuses"] == [9, 255, 351]
    assert journal.entries[0][2]["before"]["document"] == plan.before.document
    assert after.fingerprint != plan.before.fingerprint
    assert key.startswith("psg-titles-2025-")


@pytest.mark.anyio
async def test_stale_plan_has_no_writes_or_journal():
    prepare, apply, repo, journal, _, _ = workflow()
    plan = await prepare.execute(evidence())
    repo.value = 2
    with pytest.raises(ValueError, match="snapshot changed"):
        await apply.execute(plan)
    assert not journal.entries


@pytest.mark.anyio
async def test_changed_policy_or_evidence_is_rejected():
    prepare, apply, _, journal, _, _ = workflow()
    plan = await prepare.execute(evidence())
    for changed in (replace(plan, source_hash="wrong"), replace(plan, policy_version="v2")):
        with pytest.raises(ValueError, match="policy changed"):
            await apply.execute(changed)
    assert not journal.entries


@pytest.mark.anyio
async def test_failed_bonus_never_marks_batch_prepared():
    prepare, apply, _, journal, bonuses, _ = workflow()
    bonuses.failed = True
    plan = await prepare.execute(evidence())
    with pytest.raises(ValueError, match="bonus calculation failed"):
        await apply.execute(plan)
    assert [state for _, state, _ in journal.entries] == ["intent"]


@pytest.mark.anyio
async def test_busy_prepare_does_not_open_a_journal():
    prepare, _, repo, journal, _, _ = workflow()
    repo.busy = True
    with pytest.raises(ValueError, match="busy"):
        await prepare.execute(evidence())
    assert not journal.entries


@pytest.mark.anyio
async def test_revert_restores_before_and_rejects_newer_activity():
    prepare, apply, repo, _, _, _ = workflow()
    plan = await prepare.execute(evidence())
    _, after = await apply.execute(plan)
    repo.value = 2
    with pytest.raises(ValueError, match="revert CAS"):
        await apply.revert(plan.before, after, evidence())
    repo.value = 1
    await apply.revert(plan.before, after, evidence())
    assert (await repo.snapshot(evidence())).fingerprint == plan.before.fingerprint
