from copy import deepcopy

import pytest

from tests.use_cases.test_simulate_active_season_position_impact import inputs, run


def published_inputs():
    data, catalog, observations = inputs()
    old = data['scores'][0]
    pid, fid = old['player_id'], old['fixture_id']
    team = catalog[0]['team_id']
    at = '2026-10-21T02:00:00+00:00'
    tag = {'decision_id': 'review', 'assertion_kind': 'curated_fixture_scoring_role',
           'source_ref': 'reviewed-source', 'policy': 'reviewed-policy', 'accepted_at': at,
           'fixture_id': fid, 'coverage': 'unknown', 'scope_key': 'season-2026'}
    old['calculation_details']['position_decision'] = tag
    assignment = {'player_id': pid, 'team_id': team, 'season': old['season'], 'position': old['position'],
        'revision_id': 'review', 'publication_batch_id': 'batch', 'status': 'accepted',
        'assertion_kind': tag['assertion_kind'], 'applicable_fixture_ids': [fid],
        'effective_from': data['fixtures'][0]['played_at'], 'effective_until': at,
        'source_ref': tag['source_ref'], 'decision_policy': tag['policy']}
    classification = {'player_id': pid, 'team_id': team, 'position': old['position'],
        'decision_id': 'review', 'batch_id': 'batch', 'scope_key': 'season-2026',
        'scope_competition_ids': [old['competition_id']], 'definition': {'coverage': 'unknown'}}
    data['assignments'], data['scope_classifications'] = [assignment], [classification]
    data['stats'] = [{'player_id': pid, 'fixture_id': fid, 'team_id': team, 'minutes': 90, 'rating': None}]
    data['published_corrections'] = [{'batch_id': 'batch', 'status': 'published', 'rules_version_id': 4,
        'after_image': deepcopy({'events': [old], 'assignments': [assignment], 'classifications': [classification], 'bonuses': []})}]
    return data, catalog, observations


def test_verified_published_metadata_is_replayed_without_waiving_numeric_parity():
    data, catalog, observations = published_inputs()
    catalog[0]['status'] = 'not_selected'
    report, _, _ = run(data, catalog, observations)
    assert report['verified_published_events'] == 1
    assert not report['blocked_competition_seasons']
    data['scores'][0]['base_points'] += 1
    with pytest.raises(ValueError, match='after-image'):
        run(data, catalog, observations)


@pytest.mark.parametrize('broken', ['image', 'assignment', 'classification', 'batch', 'time', 'team', 'tag'])
def test_published_metadata_must_have_exact_current_identity_context_and_history(broken):
    data, catalog, observations = published_inputs()
    catalog[0]['status'] = 'not_selected'
    if broken == 'image': data['scores'][0]['calculation_details']['position_decision']['coverage'] = 'invented'
    if broken == 'assignment': data['assignments'] = []
    if broken == 'classification': data['scope_classifications'] = []
    if broken == 'batch': data['published_corrections'][0]['status'] = 'reverted'
    if broken == 'team': data['stats'][0]['team_id'] += 1
    if broken == 'time':
        for a in [data['assignments'][0], data['published_corrections'][0]['after_image']['assignments'][0]]:
            a['effective_from'] = '2027-01-01T00:00:00+00:00'
    if broken == 'tag':
        for score in [data['scores'][0], data['published_corrections'][0]['after_image']['events'][0]]:
            score['calculation_details']['position_decision']['accepted_at'] = 'invalid'
    if broken=='image':
        with pytest.raises(ValueError,match='after-image'):run(data,catalog,observations)
        return
    report, _, _ = run(data, catalog, observations)
    assert not report['verified_published_events']
    assert report['parity']['calculation_details_mismatch_ids']


def test_a_second_batch_cannot_touch_existing_published_events_without_succession():
    data, catalog, observations = published_inputs()
    with pytest.raises(ValueError, match='succession'):
        run(data, catalog, observations)
    catalog[0]['status'] = 'not_selected'
    data['published_corrections'].append(deepcopy(data['published_corrections'][0]))
    with pytest.raises(ValueError, match='Overlapping'):
        run(data, catalog, observations)


def test_exact_published_bonus_can_be_preserved_when_original_achievement_is_absent():
    data, catalog, observations = inputs()
    old = data['rollups'][0]
    bonus = {'id': 99, 'player_id': old['player_id'], 'team_id': old['team_id'], 'competition_id': old['competition_id'],
        'season': old['season'], 'achievement_id': 123, 'final_bonus': 0,
        'calculation_details': {'rank_in_team': 1, 'final_bonus': 0}}
    data['bonuses'] = [bonus]
    data['published_corrections'] = [{'batch_id': 'batch', 'status': 'published', 'rules_version_id': 4,
        'after_image': {'events': [], 'bonuses': [deepcopy(bonus)]}}]
    catalog[0]['status'] = 'not_selected'
    report, _, _ = run(data, catalog, observations)
    assert report['verified_published_bonuses'] == 1
    assert report['published_bonus_model_drift'][0]['model_available'] is False
    assert not report['parity']['bonus_errors']
    catalog[0]['status'] = 'candidate'
    with pytest.raises(ValueError, match='bonus component'):
        run(data, catalog, observations)
    catalog[0]['status'] = 'not_selected'
    data['published_corrections'] = []
    report, _, _ = run(data, catalog, observations)
    assert report['parity']['bonus_errors'] and report['blocked_competition_seasons']


@pytest.mark.parametrize('kind', ['events', 'bonuses'])
def test_owned_published_rows_cannot_disappear_or_fall_back_to_current_model(kind):
    data, catalog, observations = published_inputs()
    catalog[0]['status']='not_selected'
    if kind=='events':
        data['scores']=[]
    else:
        old=data['rollups'][0]
        expected={'id':99,'player_id':old['player_id'],'team_id':old['team_id'],
            'competition_id':old['competition_id'],'season':old['season'],'achievement_id':123,
            'final_bonus':100,'calculation_details':{'rank_in_team':1}}
        data['published_corrections'][0]['after_image']['bonuses']=[expected]
        data['bonuses']=[dict(expected,final_bonus=0)]
    with pytest.raises(ValueError,match='after-image'):
        run(data,catalog,observations)
