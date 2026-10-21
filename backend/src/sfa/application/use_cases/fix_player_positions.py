"""Retired legacy entrypoint. Statistics are not position evidence."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FixPlayerPositionsResult:
    gk_fixed: int
    dc_fixed: int
    known_positions_fixed: int
    total_fixed: int


def classify_player_from_stats(
    avg_saves: float, avg_interceptions: float, avg_goals: float, match_count: int,
) -> None:
    """Compatibility shim: statistics never propose a position."""
    return None


class FixPlayerPositionsUseCase:
    def __init__(self, session: object) -> None:
        pass

    async def execute(self) -> FixPlayerPositionsResult:
        raise RuntimeError("Statistical position repair is retired; use verified lineup evidence")
