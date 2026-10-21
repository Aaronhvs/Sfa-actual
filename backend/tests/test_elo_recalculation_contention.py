"""Contention must defer work, preserving its arguments and freeing the worker."""
import pytest
from celery.exceptions import Retry

from sfa.tasks import elo_tasks


class BusySession:
    def __init__(self):
        self.statements = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def scalar(self, statement, params):
        self.statements.append(str(statement))
        return False


@pytest.mark.anyio
@pytest.mark.parametrize("national", [False, True])
async def test_busy_pool_exits_without_waiting_or_unlocking_another_owner(monkeypatch, national):
    from sfa.infrastructure import database

    session = BusySession()
    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: session)
    with pytest.raises(elo_tasks.EloRecalculationBusyError, match="already running"):
        if national:
            await elo_tasks._run_elo_update_then_recalculate("2026", [350], 4, None, "national_elo_v1")
        else:
            await elo_tasks._run_elo_pools_then_recalculate("2026", 4, [1, 10], [])
    assert session.closed
    assert session.statements == ["SELECT pg_try_advisory_lock(:key)"]


def test_busy_task_retries_once_without_losing_the_requested_scope(monkeypatch):
    calls, retries = [], []

    async def busy(**kwargs):
        calls.append(kwargs)
        raise elo_tasks.EloRecalculationBusyError("owner running")

    def retry(**kwargs):
        retries.append(kwargs)
        raise Retry("deferred")

    monkeypatch.setattr(elo_tasks, "_run_elo_pools_then_recalculate", busy)
    monkeypatch.setattr(elo_tasks.apply_elo_pools_then_recalculate_task, "retry", retry)
    with pytest.raises(Retry):
        elo_tasks.apply_elo_pools_then_recalculate_task.run("2026", 4, [1, 10], [], False)
    assert calls == [{"season": "2026", "rules_version_id": 4, "club_competition_ids": [1, 10],
                      "national_competition_ids": [], "force_recalculate": False}]
    assert len(retries) == 1
    assert retries[0]["countdown"] == 60 and retries[0]["max_retries"] == 3
