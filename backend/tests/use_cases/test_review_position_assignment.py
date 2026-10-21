from __future__ import annotations

import pytest

from sfa.application.use_cases.review_position_assignment import ReviewPositionAssignmentUseCase
from sfa.domain.player_positions.ports import PositionIdentityRecord, PositionReferenceRepository


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeReferenceRepository:
    def __init__(self):
        self.player = PositionIdentityRecord(123, 987, "EXT", "apifootball", "MCO")
        self.accepted = set()
        self.calls = []

    async def identity(self, player_id):
        return self.player if self.player and self.player.player_id == player_id else None

    async def accept_reference(self, player_id, position, revision_id, source_ref, statement, accepted_at, actor,
                               decision_status):
        self.calls.append((player_id, position, revision_id, source_ref, statement,
                           accepted_at, actor, decision_status))
        inserted = revision_id not in self.accepted
        self.accepted.add(revision_id)
        return inserted


def arguments(**overrides):
    return {"player_id": 123, "external_id": 987, "position": "MCO", "source_ref": "user:session-quote:sha256",
            "statement": "Confirmed usual attacking midfield role", "accepted_at": "2026-10-18T12:00:00+00:00",
            "actor": "user_confirmation", **overrides}


@pytest.mark.anyio
async def test_current_specific_reference_is_by_identity_and_idempotent_without_publication():
    repository = FakeReferenceRepository()
    assert isinstance(repository, PositionReferenceRepository)
    uc = ReviewPositionAssignmentUseCase(repository)
    first = await uc.execute(**arguments())
    second = await uc.execute(**arguments(accepted_at="2026-10-18T14:00:00+00:00"))
    assert first["revision_id"] == second["revision_id"]
    assert first["inserted"] and not second["inserted"]
    assert not first["published"] and not first["retroactive_effect"]
    assert repository.player.stored_position == "EXT"
    assert first["status"] == "accepted"


@pytest.mark.anyio
async def test_new_reference_that_changes_effective_public_position_remains_draft():
    repository = FakeReferenceRepository()
    repository.player = PositionIdentityRecord(123, 987, "MC", "apifootball", "MC")
    result = await ReviewPositionAssignmentUseCase(repository).execute(**arguments(position="DEL"))
    assert result["status"] == "draft"
    assert repository.calls[-1][-1] == "draft"
    assert not result["published"]


@pytest.mark.anyio
@pytest.mark.parametrize("changes", [
    {"external_id": 111}, {"player_id": 222}, {"position": "Midfielder"}, {"source_ref": ""},
    {"statement": " "}, {"actor": ""}, {"accepted_at": "2026-10-18T12:00:00"},
])
async def test_reference_requires_identity_specificity_and_provenance(changes):
    repository = FakeReferenceRepository()
    with pytest.raises(ValueError):
        await ReviewPositionAssignmentUseCase(repository).execute(**arguments(**changes))
    assert repository.calls == []
