from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.position_mapping import KNOWN_POSITIONS
from sfa.infrastructure.models.enums import Position

logger = logging.getLogger(__name__)

_ADMIN_POSITION_FIXES: dict[str, Position] = {
    **KNOWN_POSITIONS,
    "Virgil van Dijk": Position.DC,
    "Antonio Rüdiger": Position.DC,
    "Marc-André ter Stegen": Position.GK,
    "Alisson": Position.GK,
    "Ederson": Position.GK,
    "Manuel Neuer": Position.GK,
    "David Raya": Position.GK,
    "Alejandro Balde": Position.LAT,
    "Jules Koundé": Position.LAT,
    "Trent Alexander-Arnold": Position.LAT,
}


@dataclass(frozen=True)
class FixPlayerPositionsResult:
    gk_fixed: int
    dc_fixed: int
    known_positions_fixed: int
    total_fixed: int


def classify_player_from_stats(
    avg_saves: float,
    avg_interceptions: float,
    avg_goals: float,
    match_count: int,
) -> Position | None:
    """Infer a player position from aggregated existing stats."""
    if avg_saves > 0:
        return Position.GK
    if match_count >= 3 and avg_interceptions > 1.0 and avg_goals < 0.05:
        return Position.DC
    return None


class FixPlayerPositionsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self) -> FixPlayerPositionsResult:
        known_positions_fixed = await self._apply_known_positions()
        gk_fixed = await self._fix_goalkeepers()
        dc_fixed = await self._fix_center_backs()
        total_fixed = known_positions_fixed + gk_fixed + dc_fixed
        logger.info(
            "[FixPlayerPositionsUseCase] known=%d gk=%d dc=%d total=%d",
            known_positions_fixed,
            gk_fixed,
            dc_fixed,
            total_fixed,
        )
        return FixPlayerPositionsResult(
            gk_fixed=gk_fixed,
            dc_fixed=dc_fixed,
            known_positions_fixed=known_positions_fixed,
            total_fixed=total_fixed,
        )

    async def _apply_known_positions(self) -> int:
        fixed = 0
        for player_name, position in _ADMIN_POSITION_FIXES.items():
            result = await self._session.execute(
                text(
                    """
                    UPDATE players
                    SET position = :position
                    WHERE name = :name
                      AND position <> :position
                    """
                ),
                {"name": player_name, "position": position.value},
            )
            fixed += result.rowcount or 0
        await self._session.flush()
        return fixed

    async def _fix_goalkeepers(self) -> int:
        result = await self._session.execute(
            text(
                """
                UPDATE players p
                SET position = 'GK'
                WHERE p.position = 'MC'
                  AND EXISTS (
                    SELECT 1 FROM player_stats ps
                    WHERE ps.player_id = p.id
                      AND ps.saves > 0
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM player_stats ps2
                    WHERE ps2.player_id = p.id
                      AND (ps2.goals > 0 OR ps2.assists > 0)
                  )
                """
            )
        )
        await self._session.flush()
        return result.rowcount or 0

    async def _fix_center_backs(self) -> int:
        result = await self._session.execute(
            text(
                """
                UPDATE players p
                SET position = 'DC'
                WHERE p.position = 'MC'
                  AND (
                    SELECT AVG(ps.interceptions)
                    FROM player_stats ps
                    WHERE ps.player_id = p.id
                  ) > 1.0
                  AND (
                    SELECT AVG(ps.goals)
                    FROM player_stats ps
                    WHERE ps.player_id = p.id
                  ) < 0.05
                  AND (
                    SELECT COUNT(*)
                    FROM player_stats ps
                    WHERE ps.player_id = p.id
                  ) >= 3
                """
            )
        )
        await self._session.flush()
        return result.rowcount or 0
