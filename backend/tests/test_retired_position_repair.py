from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from sfa.api.v1.admin import router
from sfa.core.dependencies import get_db, get_fix_player_positions_use_case, require_admin_key


@pytest.fixture
def anyio_backend():
    return "asyncio"


class UnusedRepair:
    async def execute(self):
        raise AssertionError("Retired heuristic must not run")


class UnusedTransaction:
    async def commit(self):
        raise AssertionError("Retired route must not commit")


@pytest.mark.anyio
@pytest.mark.parametrize("route", ["/admin/players/fix-positions", "/admin/fix-player-positions"])
async def test_legacy_position_repair_routes_are_explicitly_retired_without_mutation(route):
    app = FastAPI()
    app.include_router(router)

    async def authorized():
        return None

    async def repair():
        return UnusedRepair()

    async def database():
        yield UnusedTransaction()

    app.dependency_overrides[require_admin_key] = authorized
    app.dependency_overrides[get_fix_player_positions_use_case] = repair
    app.dependency_overrides[get_db] = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(route)
    assert response.status_code == 410
    assert "evidence-based" in response.json()["detail"]
