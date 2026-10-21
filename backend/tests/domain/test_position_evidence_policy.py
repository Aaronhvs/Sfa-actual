from copy import deepcopy

import pytest

from sfa.domain.player_positions.evidence_policy import (
    acquisition_tier,
    active_provider_versions,
    provider_family,
    retained_provider_versions,
)


@pytest.mark.parametrize("raw,expected", [("G", "GK"), ("D", "DC"), ("M", "MC"),
                                         ("F", "DEL"), ("Forward", "DEL"), (None, None), ("?", None)])
def test_family_is_generic_and_absence_is_not_mc(raw, expected):
    assert provider_family(raw) == expected


def test_under_three_overrides_top300_priority_and_later_cohort_is_separate():
    row = {"rank": 87, "appearances": 2, "status": "insufficient_evidence"}
    assert acquisition_tier(row, 2) is None
    assert acquisition_tier(row | {"appearances": 3}, 3) == 1
    assert acquisition_tier(row | {"rank": 400, "appearances": 6}, 6) == 2
    assert acquisition_tier(row | {"rank": 400, "appearances": 5}, 5) is None


def test_cache_timestamp_never_supersedes_and_authoritative_revision_retains_history():
    old = {"id": 1, "fixture_id": 1552785, "team_id": 96, "payload_hash": "old"}
    cache = old | {"id": 2, "payload_hash": "cache", "received_at": "2099-01-01"}
    assert len(active_provider_versions((old, cache))[0]) == 2
    new = old | {"id": 3, "payload_hash": "new", "authority": "api-football-direct-validated",
                 "fetched_at": "2026-10-20T12:00:00+00:00"}
    before = deepcopy((old, cache, new))
    active, ledger = active_provider_versions((old, cache, new))
    assert active == (new,)
    assert ledger[0]["supersedes"] == [1, 2]
    assert (old, cache, new) == before
    conflicting = new | {"id": 4, "payload_hash": "contradiction"}
    assert len(active_provider_versions((old, new, conflicting))[0]) == 3


def test_durable_arbitration_is_reused_without_the_original_local_refresh_file():
    old={'id':1,'fixture_id':10,'team_id':20,'payload_hash':'old','payload':{'formation':'4-4-2'}}
    latest=old|{'id':2,'payload_hash':'new','payload':{'formation':'4-2-3-1'}}
    snapshot={'snapshots':[old,latest],'lineup_arbitrations':[{'active_snapshot_id':2,'fixture_id':10,
        'team_id':20,'fetched_at':'2026-10-21T00:00:00+00:00'}]}
    active,_=retained_provider_versions(snapshot)
    assert len(active)==1 and active[0]['id']==2
    # Raw response hashes can differ from normalized team payload hashes while
    # retaining the same actual formation/slots; receipt format is not a conflict.
    duplicate=latest|{'id':'local-file','payload_hash':'whole-http-response',
                      'authority':'api-football-direct-validated','fetched_at':'2026-10-21T00:00:00+00:00'}
    assert len(retained_provider_versions(snapshot,(duplicate,))[0])==1
