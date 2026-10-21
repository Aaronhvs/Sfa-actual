from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sfa.domain.player_positions.ports import PositionReferenceRepository


class ReviewPositionAssignmentUseCase:
    """Record an explicit current habitual-role reference by verified stable IDs.

    This operation preserves an accepted reference; it does not publish labels,
    backdate a sporting claim, or recalculate scores. New scoring-impacting
    assignments go through correction simulation/publication separately.
    """

    def __init__(self, repository: PositionReferenceRepository) -> None:
        self._repository = repository

    async def execute(
        self, *, player_id: int, external_id: int, position: str, source_ref: str,
        statement: str, accepted_at: str, actor: str,
    ) -> dict:
        if position not in {"GK", "DC", "LAT", "MC", "MCO", "EXT", "DEL"}:
            raise ValueError("Unsupported specific SFA position")
        if not all(value.strip() for value in (source_ref, statement, actor)):
            raise ValueError("Reference provenance and actor required")
        if datetime.fromisoformat(accepted_at).tzinfo is None:
            raise ValueError("Reference acceptance time must include a timezone")
        identity = await self._repository.identity(player_id)
        if identity is None or identity.external_id != external_id:
            raise ValueError("Internal/external player identity mismatch")
        revision = hashlib.sha256(json.dumps({
            "player_id": player_id, "external_id": external_id, "position": position,
            "source_ref": source_ref, "statement": statement, "scope": "current_habitual_reference",
        }, sort_keys=True).encode()).hexdigest()
        decision_status = ("accepted" if position == (identity.legacy_effective_position or identity.stored_position)
                           else "draft")
        inserted = await self._repository.accept_reference(
            player_id, position, revision, source_ref, statement, accepted_at, actor, decision_status,
        )
        return {"player_id": player_id, "revision_id": revision, "position": position,
                "inserted": inserted, "status": decision_status, "published": False, "retroactive_effect": False}
