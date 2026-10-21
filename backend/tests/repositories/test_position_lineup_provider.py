from __future__ import annotations

import json

import httpx
import pytest

from sfa.infrastructure.providers.position_lineup_provider import PositionLineupProvider


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_status_discards_account_fields_and_keeps_only_quota_and_subscription():
    def respond(request):
        assert request.url.path == "/status"
        return httpx.Response(200, json={"response": {"account": {"email": "private@example.test"},
                                                    "subscription": {"active": True},
                                                    "requests": {"current": 100, "limit_day": 7500}}},
                              headers={"x-ratelimit-requests-remaining": "7400", "x-ratelimit-remaining": "299"})
    async with httpx.AsyncClient(base_url="https://provider.test", transport=httpx.MockTransport(respond)) as client:
        result = await PositionLineupProvider(client).status()
    assert result.daily_remaining == 7400
    assert result.minute_remaining == 299
    assert result.minute_limit is None
    assert "private" not in result.body
    assert json.loads(result.body)["active"] is True


@pytest.mark.anyio
async def test_lineup_http_is_single_endpoint_single_attempt_with_raw_payload_retained():
    requests = []

    def respond(request):
        requests.append(request)
        assert str(request.url) == "https://provider.test/fixtures/lineups?fixture=123"
        return httpx.Response(429, content=b'{"errors":{"limit":"hit"}}')
    async with httpx.AsyncClient(base_url="https://provider.test", transport=httpx.MockTransport(respond)) as client:
        result = await PositionLineupProvider(client).fetch_lineups(123)
    assert len(requests) == 1
    assert result.http_status == 429
    assert result.fixture_id == 123
    assert json.loads(result.body)["errors"]


@pytest.mark.anyio
async def test_transport_error_does_not_retry_or_expose_request_credentials():
    requests = []

    def timeout(request):
        requests.append(request)
        raise httpx.ReadTimeout("sensitive transport detail", request=request)
    async with httpx.AsyncClient(base_url="https://provider.test", transport=httpx.MockTransport(timeout)) as client:
        result = await PositionLineupProvider(client).fetch_lineups(123)
    assert len(requests) == 1
    assert result.transport_error == "ReadTimeout"
    assert "sensitive" not in str(result)
