import httpx
import pytest

from sfa.infrastructure.providers.api_football import APIFootballProvider


class FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def get(self, endpoint, params=None):
        self.calls += 1
        return httpx.Response(200, request=httpx.Request("GET", "https://example.test"), json=self.payload)


class ProviderWithFakeClient(APIFootballProvider):
    def __init__(self, payload):
        super().__init__("key", "https://example.test")
        self.client = FakeHttpClient(payload)

    def _get_client(self):
        return self.client


@pytest.mark.anyio
async def test_provider_errors_cannot_be_treated_as_an_empty_timeline():
    provider = ProviderWithFakeClient({"errors": {"parameters": "Invalid fixture"}, "response": []})
    with pytest.raises(RuntimeError, match="returned errors"):
        await provider.fetch_fixture_events(123)
    assert provider.client.calls == 1


@pytest.mark.anyio
async def test_malformed_goal_cannot_be_silently_dropped_from_timeline():
    provider = ProviderWithFakeClient({"errors": [], "response": [{"type": "Goal", "detail": "Normal Goal"}]})
    with pytest.raises(ValueError, match="partial event timeline"):
        await provider.fetch_fixture_events(123)
