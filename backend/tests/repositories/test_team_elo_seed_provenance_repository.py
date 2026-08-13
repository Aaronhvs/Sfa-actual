from datetime import date

from sfa.domain.scoring_ports import EloSeedProvenanceDTO
from sfa.infrastructure.repositories.team_strength_repository import (
    _deserialize_seed_provenance,
    _serialize_seed_provenance,
)


def test_clubelo_seed_provenance_round_trip() -> None:
    provenance = EloSeedProvenanceDTO(
        resolution_method="clubelo_history_prior",
        cutoff=date(2025, 7, 7),
        source_reference="http://api.clubelo.com/Cardiff",
        source_entity="Cardiff",
        source_country="ENG",
        source_valid_from=date(2025, 5, 29),
        source_valid_to=date(2025, 7, 5),
        history_age_days=2,
        payload_sha256="a" * 64,
    )

    assert _deserialize_seed_provenance(_serialize_seed_provenance(provenance)) == provenance


def test_empty_legacy_provenance_remains_explicitly_unverified() -> None:
    assert _deserialize_seed_provenance({}) is None
