import importlib
from types import SimpleNamespace

task_module = importlib.import_module("sfa.tasks.run_full_recalculation_task")
config_module = importlib.import_module("sfa.core.config")
explanations_task_module = importlib.import_module("sfa.tasks.generate_ranking_explanations_task")


class FakeGenerateRankingExplanationsTask:
    def __init__(self) -> None:
        self.calls = []

    def delay(self, *args):
        self.calls.append(args)
        return SimpleNamespace(id="task-123")


def test_queue_world_cup_explanations_uses_incremental_refresh(monkeypatch):
    fake_task = FakeGenerateRankingExplanationsTask()
    monkeypatch.setattr(
        explanations_task_module,
        "generate_ranking_explanations_task",
        fake_task,
    )
    monkeypatch.setattr(
        config_module,
        "get_settings",
        lambda: SimpleNamespace(AI_EXPLANATIONS_TOP_N=3),
    )

    task_id = task_module._queue_ranking_explanations_after_recalculation("2026", 4)

    assert task_id == "task-123"
    assert fake_task.calls == [
        ("2026", 4, 350, "world_cup", 3, False, True),
    ]


def test_queue_global_explanations_for_non_world_cup_season(monkeypatch):
    fake_task = FakeGenerateRankingExplanationsTask()
    monkeypatch.setattr(
        explanations_task_module,
        "generate_ranking_explanations_task",
        fake_task,
    )
    monkeypatch.setattr(
        config_module,
        "get_settings",
        lambda: SimpleNamespace(AI_EXPLANATIONS_TOP_N=10),
    )

    task_id = task_module._queue_ranking_explanations_after_recalculation("2025", 4)

    assert task_id == "task-123"
    assert fake_task.calls == [
        ("2025", 4, None, "ranking", 10, False, True),
    ]
