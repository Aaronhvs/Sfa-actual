from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sfa.domain.player_positions.ports import PositionEvidenceRecorder, RecordPositionEvidenceResult


class PositionEvidenceCaptureAdapter:
    """Awaitable input adapter shared by HTTP acquisition and scheduled work.

    Commit before the caller caches a response. The request's own transaction
    cannot accidentally roll back evidence which has already been fetched.
    """

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession],
        use_case_factory: Callable[[AsyncSession], PositionEvidenceRecorder],
    ) -> None:
        self._sessions = sessions
        self._factory = use_case_factory

    async def execute(
        self, fixture_external_id: int, payload_json: str, source_ref: str, received_at: str,
    ) -> RecordPositionEvidenceResult:
        async with self._sessions() as session, session.begin():
            return await self._factory(session).execute(fixture_external_id, payload_json, source_ref, received_at)
