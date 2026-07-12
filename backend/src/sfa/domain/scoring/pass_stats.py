from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedPassStats:
    completed: int
    accuracy_pct: float


def normalize_pass_stats(
    passes_total: int | None,
    passes_completed_or_accuracy: float | None,
    *,
    value_is_completed: bool = True,
) -> NormalizedPassStats:
    total = max(0, int(passes_total or 0))
    raw = max(0.0, float(passes_completed_or_accuracy or 0.0))
    if total <= 0 or raw <= 0:
        return NormalizedPassStats(completed=0, accuracy_pct=0.0)

    if value_is_completed:
        completed = min(total, int(round(raw)))
        return NormalizedPassStats(
            completed=completed,
            accuracy_pct=completed * 100.0 / total,
        )

    accuracy_pct = min(100.0, raw)
    return NormalizedPassStats(
        completed=int(round(total * accuracy_pct / 100.0)),
        accuracy_pct=accuracy_pct,
    )
