from dataclasses import replace

import pytest

from sfa.application.use_cases.apply_season_event_integrity import ApplySeasonEventIntegrityUseCase
from sfa.application.use_cases.prepare_season_event_integrity import PrepareSeasonEventIntegrityUseCase
from sfa.domain.event_integrity import Action, ActionRevision, FixtureSnapshot, IntegrityPlan
from sfa.domain.event_integrity_ports import IntegrityJournalPort, SeasonEventIntegrityRepositoryPort


class FakeRepository(SeasonEventIntegrityRepositoryPort):
    def __init__(self):
        self.current = FixtureSnapshot(1, 123, 10, "2025", 541, 81, 0, 0, (), (), "before")
        self.applied = []

    async def snapshot(self, fixture_id):
        return self.current

    async def apply(self, plan):
        self.applied.append(plan)
        self.current = replace(self.current, fingerprint="after")
        return len(plan.changes)

    async def get_context_conflict_fixture_ids(self):
        return ()


class FakeJournal(IntegrityJournalPort):
    def __init__(self):
        self.records = []

    async def write(self, key, state, payload):
        self.records.append((key, state, payload))


def plan():
    return IntegrityPlan(
        1, 123, "before", "source", (ActionRevision(None, Action(888, 2, 29, "GOAL_PENALTY", "0:0", 0, False, 1)),), ()
    )


@pytest.mark.anyio
async def test_apply_writes_before_and_after_without_committing():
    repository, journal = FakeRepository(), FakeJournal()
    assert isinstance(repository, SeasonEventIntegrityRepositoryPort)
    assert isinstance(journal, IntegrityJournalPort)
    assert await ApplySeasonEventIntegrityUseCase(repository, journal).execute(plan()) == 1
    assert [r[1] for r in journal.records] == ["intent", "prepared"]
    assert '"before"' in journal.records[0][2]
    assert '"after"' in journal.records[1][2]


@pytest.mark.anyio
async def test_apply_rejects_stale_snapshot_before_any_write():
    repository, journal = FakeRepository(), FakeJournal()
    repository.current = replace(repository.current, fingerprint="concurrent-change")
    with pytest.raises(ValueError, match="changed"):
        await ApplySeasonEventIntegrityUseCase(repository, journal).execute(plan())
    assert not repository.applied
    assert not journal.records


@pytest.mark.anyio
async def test_apply_rejects_pending_plan():
    repository, journal = FakeRepository(), FakeJournal()
    with pytest.raises(ValueError, match="pending"):
        await ApplySeasonEventIntegrityUseCase(repository, journal).execute(replace(plan(), pending=("missing",)))
    assert not repository.applied


@pytest.mark.anyio
async def test_no_change_does_not_touch_journal_or_repository():
    repository, journal = FakeRepository(), FakeJournal()
    assert await ApplySeasonEventIntegrityUseCase(repository, journal).execute(replace(plan(), changes=())) == 0
    assert not repository.applied
    assert not journal.records


@pytest.mark.anyio
async def test_prepare_is_read_only_and_reports_missing_evidence():
    repository = FakeRepository()
    result = await PrepareSeasonEventIntegrityUseCase(repository).execute(
        1,
        {
            "parameters": {"fixture": "123"},
            "errors": [],
            "results": 0,
            "response": [],
        },
    )
    assert result.pending == ("missing_player_stats",)
    assert not repository.applied
