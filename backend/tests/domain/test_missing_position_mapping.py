import pytest

from sfa.domain.position_mapping import map_position
from sfa.infrastructure.models.enums import Position


@pytest.mark.parametrize("raw", [None, "", " ", "Unsupported", "Not available"])
def test_missing_or_unknown_family_is_not_a_midfielder(raw):
    assert map_position("Arbitrary Player", raw) is None


def test_name_override_does_not_create_an_observation_when_provider_position_is_absent():
    assert map_position("Harry Kane", "") is None


@pytest.mark.parametrize("raw,position", [("G", Position.GK), ("Goalkeeper", Position.GK),
                                         ("D", Position.DC), ("F", Position.DEL), ("M", Position.MC)])
def test_explicit_provider_families_remain_recognizable(raw, position):
    assert map_position("Arbitrary Player", raw) == position
