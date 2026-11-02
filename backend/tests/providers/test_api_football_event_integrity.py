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


@pytest.mark.anyio
async def test_provider_retains_explicit_shootout_phase_below_minute_120():
    from sfa.domain.scoring.services import is_shootout_attempt_event

    event = {"type": "Goal", "detail": "Penalty", "comments": "Penalty Shootout",
             "time": {"elapsed": 91, "extra": None}, "team": {"id": 50},
             "player": {"id": 631, "name": "Foden"}, "assist": {"id": None, "name": None}}
    provider = ProviderWithFakeClient({"errors": [], "response": [event]})
    rows = await provider.fetch_fixture_events(123)
    assert rows[0].minute == 91 and rows[0].player_external_id == 631
    assert rows[0].comments == "Penalty Shootout"
    assert is_shootout_attempt_event(rows[0])
