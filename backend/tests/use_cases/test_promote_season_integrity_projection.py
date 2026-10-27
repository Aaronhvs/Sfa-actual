import pytest

from sfa.application.use_cases.promote_season_integrity_projection import (
    PromoteSeasonIntegrityProjectionUseCase,
    RevertSeasonIntegrityProjectionUseCase,
)
from sfa.domain.event_integrity_ports import IntegrityPublicationSnapshot, SeasonIntegrityPublicationRepositoryPort
from tests.use_cases.test_season_event_integrity import FakeJournal


class FakePublicationRepository(SeasonIntegrityPublicationRepositoryPort):
    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure

    async def lock(self):
        self.calls.append("lock")
        if self.failure == "lock":
            raise ValueError("busy")

    async def validate(self, reverting):
        self.calls.append(("validate", reverting))
        if self.failure == "validate":
            raise ValueError("CAS")
        return IntegrityPublicationSnapshot("before", (("fixtures", 2840),))

    async def replace(self, reverting):
        self.calls.append(("replace", reverting))
        if self.failure == "replace":
            raise ValueError("guard")
        return IntegrityPublicationSnapshot("after", (("fixtures", 2840),))


@pytest.mark.anyio
@pytest.mark.parametrize("reverting", [False, True])
async def test_publication_lock_cas_and_durable_after_precede_external_commit(reverting):
    repository, journal = FakePublicationRepository(), FakeJournal()
    assert isinstance(repository, SeasonIntegrityPublicationRepositoryPort)
    kind = RevertSeasonIntegrityProjectionUseCase if reverting else PromoteSeasonIntegrityProjectionUseCase
    key, after = await kind(repository, journal).execute()
    assert repository.calls == ["lock", ("validate", reverting), ("replace", reverting)]
    assert [r[1] for r in journal.records] == ["intent", "prepared"]
    assert after.fingerprint == "after"
    assert key.startswith("season-2025-")


@pytest.mark.anyio
@pytest.mark.parametrize("failure,records", [("lock", 0), ("validate", 0), ("replace", 1)])
async def test_failed_gate_does_not_claim_a_prepared_publication(failure, records):
    repository, journal = FakePublicationRepository(failure), FakeJournal()
    with pytest.raises(ValueError):
        await PromoteSeasonIntegrityProjectionUseCase(repository, journal).execute()
    assert len(journal.records) == records
