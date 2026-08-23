from __future__ import annotations

import httpx
import pytest

from sfa.domain.ingestion_ports import ProviderDailyQuotaExceededError
from sfa.infrastructure.providers.api_football import APIFootballProvider


class FakeHttpClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls = 0

    async def get(self, endpoint: str, params: dict | None = None) -> httpx.Response:
        self.calls += 1
        return self.responses.pop(0)


class ProviderWithFakeClient(APIFootballProvider):
    def __init__(self, client: FakeHttpClient) -> None:
        super().__init__("key", "https://example.test")
        self.fake_client = client

    def _get_client(self) -> FakeHttpClient:
        return self.fake_client


@pytest.mark.anyio
async def test_daily_quota_error_is_typed_and_not_retried() -> None:
    request = httpx.Request("GET", "https://example.test/fixtures")
    response = httpx.Response(
        200,
        request=request,
        json={"errors": {"requests": "You have reached the request limit for the day"}},
    )
    client = FakeHttpClient([response])
    provider = ProviderWithFakeClient(client)

    with pytest.raises(ProviderDailyQuotaExceededError, match="daily request limit"):
        await provider._get("fixtures", {"date": "2026-08-23"})

    assert client.calls == 1
