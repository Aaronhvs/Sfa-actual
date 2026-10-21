import pytest

from sfa.domain.ranking_eligibility import ranking_min_matches


@pytest.mark.parametrize("maximum,minimum", [(0, 1), (1, 1), (4, 1), (5, 2), (12, 3), (13, 4), (30, 5)])
def test_dynamic_minimum(maximum, minimum):
    assert ranking_min_matches(maximum) == minimum
