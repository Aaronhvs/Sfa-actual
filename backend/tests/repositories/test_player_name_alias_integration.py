"""Explicit clone-only HTTP regressions; never touches production or a provider."""
import os
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(os.getenv('POSITION_VALIDATION_CLONE')!='1',
    reason='Requires restored PostgreSQL position-validation clone')]


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.parametrize('params', [{'scope':'season-2026'}, {'season':'2026'}, {'scope':'all'}])
async def test_full_name_search_preserves_display_points_counts_and_pagination(params):
    from sfa.core.dependencies import get_enrich_player_name_aliases_use_case
    from sfa.domain.player_name_aliases import PlayerNameProfileDTO
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.main import app
    async with AsyncSessionLocal() as s:
        assert (await s.scalar(text('SELECT current_database()'))).startswith('sfa_positions_validation_')
        await get_enrich_player_name_aliases_use_case(s).execute((PlayerNameProfileDTO(568001,full_name='Xavi Espart'),),
            provider='official-club-reviewed', source_ref='https://club.example;actor=clone-regression',
            captured_at=datetime.now(timezone.utc))
        await s.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://validation') as client:
        before=(await client.get('/api/v1/ranking',params=params|{'name':'Espart','limit':50})).json()
        for name in ('Xavi','Xavi Espart',' Espart  XAVI ','X. Espart'):
            response=await client.get('/api/v1/ranking',params=params|{'name':name,'limit':50})
            assert response.status_code==200,response.text
            data=response.json()
            expected=next(r for r in before['ranking'] if r['id']==1022093)
            assert next(r for r in data['ranking'] if r['id']==1022093)==expected
            assert data['total']==len(data['ranking']) and data['min_matches']==0
            assert len({r['id'] for r in data['ranking']})==len(data['ranking'])
        data=(await client.get('/api/v1/ranking',params=params|{'name':'Xavi Espart','limit':1,'offset':1})).json()
        assert data['ranking']==[] and data['total']==1
