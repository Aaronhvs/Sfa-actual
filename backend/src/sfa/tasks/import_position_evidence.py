from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sfa.domain.player_positions.ports import PositionEvidenceRecorder


class ImportPositionEvidenceAdapter:
    """Import retained, hashed evidence and explicit baseline-compatible references.

    References share one transaction and cannot partly apply if an identity is
    wrong. Lineups are independently idempotent, so large imports can resume.
    No scoring writer or external provider is available to this adapter.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession], recorder: PositionEvidenceRecorder,
                 review_factory: Callable) -> None:
        self._sessions = sessions
        self._recorder = recorder
        self._review_factory = review_factory

    async def execute(self, snapshot_json: str, reference_json: str) -> dict:
        snapshot, references = json.loads(snapshot_json), json.loads(reference_json)
        if snapshot.get("schema") != "sfa-position-audit-snapshot-v1":
            raise ValueError("Unsupported retained evidence schema")
        reference_hash = hashlib.sha256(reference_json.encode()).hexdigest()
        source_ref = f"curated-document:sha256:{reference_hash}"
        accepted_at = datetime.now(timezone.utc).isoformat()
        reviewed = []
        async with self._sessions() as session, session.begin():
            use_case = self._review_factory(session)
            for reference in references["references"]:
                reviewed.append(await use_case.execute(
                    player_id=reference["player_id"], external_id=reference["provider_player_id"],
                    position=reference["position"], source_ref=source_ref,
                    statement=references["statement"], accepted_at=accepted_at,
                    actor="user_confirmation",
                ))
        captures = []
        for entry in snapshot["cache"]:
            payload = entry["payload"]
            captures.append(await self._recorder.execute(
                payload["fixture"]["external_id"], json.dumps(payload, sort_keys=True),
                f"retained-corpus:{entry['key']}", entry.get("fetched_at", snapshot["captured_at"]),
            ))
        return {"reference_sha256": reference_hash,
                "snapshot_sha256": hashlib.sha256(snapshot_json.encode()).hexdigest(),
                "references": reviewed, "fixture_results": [r.__dict__ for r in captures],
                "http_calls": 0, "scoring_writes": 0, "publication_enabled": False}
