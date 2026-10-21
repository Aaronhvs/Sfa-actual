import json
from pathlib import Path

from sfa.application.use_cases.audit_active_season_positions import AuditActiveSeasonPositionsUseCase
from sfa.application.use_cases.prepare_season_position_correction import pilot_eligible


def test_espart_latest_verified_lineup_resolves_conflict_and_supports_lateral_in_eight_starts():
    path=Path(__file__).parents[1]/'fixtures/player_positions/espart-eight-starts-2026.json'
    data=json.loads(path.read_text('utf8'))
    supplementary=tuple(data.pop('supplementary'))
    before=AuditActiveSeasonPositionsUseCase().execute(data)
    assert json.loads(before.catalog_json)[0]['status']=='ambiguous'
    result=AuditActiveSeasonPositionsUseCase().execute(data,supplementary=supplementary)
    row=json.loads(result.catalog_json)[0]
    assert row['player_id']==1022093 and row['stored_position']=='MC'
    assert row['status']=='candidate' and row['proposed_position']=='LAT'
    assert row['recent']['observations']==8 and row['recent']['primary_side']=='LEFT'
    assert row['recent']['position_distribution']==[{'value':'LAT','count':8,'share':1.0}]
    assert not row['recent']['conflicting_fixture_ids'] and pilot_eligible(row)
    observations=json.loads(result.observations_json)
    assert {o['projection'] for o in observations if o['player_id']==1022093}=={'LAT'}
    latest=[o for o in observations if o['player_id']==1022093 and o['fixture_id']==851925]
    assert len(latest)==1 and latest[0]['role']=='FB' and latest[0]['side']=='RIGHT'
    # Longitudinal evidence is still a candidate; publication needs separate approval.
    assert not row['publishable']
