import json
from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from sfa.application.use_cases.prepare_season_position_correction import PrepareSeasonPositionCorrectionUseCase, pilot_eligible
from sfa.application.use_cases.publish_season_position_correction import PublishSeasonPositionCorrectionUseCase
from sfa.application.use_cases.simulate_active_season_position_impact import SimulateActiveSeasonPositionImpactUseCase
from sfa.domain.player_positions.publication import PositionPublicationResult, digest
from tests.use_cases.test_simulate_active_season_position_impact import inputs


def prepared_inputs():
    data, catalog, observations = inputs()
    pid, team, comp = catalog[0]['player_id'], catalog[0]['team_id'], data['fixtures'][0]['competition_id']
    data.update(scope={'key':'season-2026', 'sources':[{'season':'2026','competition_ids':[comp]}]},
                players=[{'id':pid,'external_id':991}], teams=[{'id':team,'external_id':992}])
    data['rollups'][0].update(id=55,rules_version_id=4)
    catalog[0].update(season='2026', appearances=7, recent={'observations':7,
        'position_distribution':[{'value':'DEL','count':6},{'value':'EXT','count':1}]},
        season_profile={'primary_position':'DEL'},
        by_competition=[{'context':{'competition_id':comp},'primary_position':'DEL','observations':7}])
    return data, catalog, observations


async def prepare(data=None, catalog=None, observations=None):
    original = prepared_inputs()
    return await PrepareSeasonPositionCorrectionUseCase(SimulateActiveSeasonPositionImpactUseCase()).execute(
        data or original[0], catalog=catalog if catalog is not None else original[1],
        observations=observations if observations is not None else original[2], evidence=[],
        source_hash='source', engine_hash='engine', accepted_at='2026-10-21T02:00:00+00:00', actor='reviewer')


@pytest.mark.anyio
async def test_prepares_fixture_scoped_history_and_separate_scope_label_without_habitual_reference():
    data, catalog, observations = prepared_inputs()
    frozen=deepcopy(data)
    plan=await prepare(data,catalog,observations)
    decision=json.loads(plan.decisions_json)[0]
    assert decision['fixture_ids']==[data['fixtures'][0]['id']]
    assert decision['assertion_kind']=='curated_fixture_scoring_role'
    classification=json.loads(plan.classifications_json)[0]
    assert classification['scope_key']=='season-2026' and classification['position']=='DEL'
    event=json.loads(plan.event_changes_json)[0]
    assert event['after']['position']=='DEL' and event['after']['final_points']!=event['before']['final_points']
    assert event['after']['calculation_details']['position_decision']['decision_id']==decision['decision_id']
    assert json.loads(plan.report_json)['actual_habitual_references_inserted']==0
    assert data==frozen and plan.batch_id==digest(asdict(plan))


@pytest.mark.parametrize('change',[
    {'status':'ambiguous'}, {'accepted_references':[{'position':'MCO'}]}, {'appearances':2},
    {'proposed_position':'GK'}, {'season_profile':{'primary_position':'EXT'}},
    {'recent':{'observations':5,'position_distribution':[{'value':'DEL','count':5}]}},
    {'recent':{'observations':8,'position_distribution':[{'value':'DEL','count':5}]}},
    {'recent':{'observations':8,'position_distribution':[{'value':'DEL','count':8}], 'conflicting_fixture_ids':[9]}}
])
@pytest.mark.anyio
async def test_pilot_rejects_weak_conflicting_or_protected_profiles(change):
    data,catalog,observations=prepared_inputs()
    catalog[0].update(change)
    assert not pilot_eligible(catalog[0])
    with pytest.raises(ValueError,match='No reviewed candidates'):await prepare(data,catalog,observations)


@pytest.mark.parametrize('scope',[
    {'key':'season-2025','sources':[{'season':'2025','competition_ids':[1]}]},
    {'key':'season-2026','sources':[{'season':'2026','competition_ids':[350]}]},
    {'key':'season-2026','sources':[{'season':'2025','competition_ids':[1]}]}
])
@pytest.mark.anyio
async def test_other_seasons_and_world_cup_are_refused(scope):
    data,catalog,observations=prepared_inputs();data['scope']=scope
    with pytest.raises(ValueError):await prepare(data,catalog,observations)


@pytest.mark.anyio
async def test_no_starting_evidence_does_not_publish_a_season_majority_over_missing_fixtures():
    with pytest.raises(ValueError,match='no complete scored fixture'):await prepare(observations=[])


@pytest.mark.anyio
async def test_failed_parity_prevents_publication():
    data,catalog,observations=prepared_inputs();data['scores'][0]['final_points']+=1
    with pytest.raises(ValueError,match='parity'):await prepare(data,catalog,observations)


@pytest.mark.anyio
async def test_manifest_loading_itself_rejects_cross_scope_rows_and_unapproved_labels():
    plan=await prepare()
    for field in ('event_changes_json','rollup_changes_json'):
        values=json.loads(getattr(plan,field));values[0]['after']['season']='2025'
        with pytest.raises(ValueError,match='scope or identity'):
            replace(plan,**{field:json.dumps(values)})
    classes=json.loads(plan.classifications_json);classes[0]['position']='MC'
    with pytest.raises(ValueError,match='Scope classifications'):
        replace(plan,classifications_json=json.dumps(classes))


class FakeSeasonRepository:
    def __init__(self):self.prior=None;self.source='source';self.applied=[];self.reverted=[]
    async def published(self,batch_id):return self.prior
    async def fingerprint(self,scope_json,rules_version_id):return self.source
    async def apply(self,plan):
        self.applied.append(plan)
        self.prior=PositionPublicationResult(plan.batch_id,'published',1,1)
        return self.prior
    async def revert(self,batch_id,actor):
        self.reverted.append((batch_id,actor))
        return PositionPublicationResult(batch_id,'reverted',1,1)


@pytest.mark.anyio
async def test_publish_is_idempotent_and_stale_or_reverted_manifests_are_refused():
    repo=FakeSeasonRepository();uc=PublishSeasonPositionCorrectionUseCase(repo);plan=await prepare()
    repo.source='stale'
    with pytest.raises(ValueError,match='changed'):await uc.execute(plan)
    assert not repo.applied
    repo.source='source'
    first=await uc.execute(plan)
    assert await uc.execute(plan)==first and len(repo.applied)==1
    repo.prior=replace(first,status='reverted')
    with pytest.raises(ValueError,match='reverted'):await uc.execute(plan)
