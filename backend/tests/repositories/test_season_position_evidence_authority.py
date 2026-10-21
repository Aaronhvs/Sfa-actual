from itertools import permutations

import pytest

from sfa.infrastructure.repositories.season_position_correction_repository import _authorities


def version(formation, at):
    return dict(fixture_id=1,team_id=2,authority='api-football-direct-validated',fetched_at=at,
                payload={'formation':formation,'start_xi':[],'substitutes':[]})


def test_latest_real_instant_wins_independent_of_order_and_old_conflicts():
    old=version('4-4-2','2026-10-20T20:00:00-03:00')
    old_other=version('4-3-3','2026-10-20T23:00:00+00:00')
    latest=version('4-2-3-1','2026-10-21T00:00:00+00:00')
    for values in permutations([old,old_other,latest]):
        assert _authorities(values)[1,2]==latest


def test_incompatible_latest_provider_tie_is_quarantined_in_both_orders():
    left=version('4-4-2','2026-10-20T20:00:00-03:00')
    right=version('4-3-3','2026-10-20T23:00:00+00:00')
    for values in permutations([left,right]):
        with pytest.raises(ValueError,match='quarantine'):_authorities(values)
