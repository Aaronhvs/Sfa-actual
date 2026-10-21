from dataclasses import asdict, replace

import pytest

from sfa.domain.player_positions.publication import PositionCorrectionPlan, PositionCorrectionRequest, digest
from sfa.domain.player_positions.resolution import PlayerPositionResolver
from tests.domain.test_position_resolution import assignment, query


def test_curated_fixture_decision_never_becomes_current_habitual_reference():
    curated=assignment(assertion_kind='curated_fixture_scoring_role', position='DEL',
                       applicable_fixture_ids=frozenset({90}), effective_until='2026-10-21T00:00:00+00:00')
    resolver=PlayerPositionResolver()
    assert resolver.resolve(query(),(curated,),()).position is None
    historic=query(purpose='historical_habitual',fixture_id=90)
    result=resolver.resolve(historic,(curated,),())
    assert result.position=='DEL' and result.basis=='accepted_curated_scoring_role'
    assert resolver.resolve(replace(historic,fixture_id=91),(curated,),()).position is None
    with pytest.raises(ValueError,match='allowlist'):
        replace(curated,applicable_fixture_ids=None)


def test_legacy_manifest_digest_keeps_its_original_request_shape():
    request=PositionCorrectionRequest(1,2,3,4,'2026','DEL',(5,), '2026-10-21T00:00:00+00:00',
                                      'source','review','actor',schema_version=1)
    plan=PositionCorrectionPlan(request,4,'input','engine','[]','[]','{}','{}')
    old=asdict(plan)
    old['request'].pop('schema_version');old['request'].pop('current_reference_json')
    assert plan.manifest_hash==digest(old)
    assert request.manifest_data==old['request']
    assert replace(plan,request=replace(request,schema_version=2)).manifest_hash!=plan.manifest_hash
