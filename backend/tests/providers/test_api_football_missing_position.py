import pytest

from sfa.infrastructure.providers.api_football import APIFootballProvider


class ProviderWithFakeClient(APIFootballProvider):
    def __init__(self, payload):
        super().__init__("test", "https://example.test")
        self.payload = payload

    async def _get(self, endpoint, params=None):
        return self.payload


@pytest.mark.anyio
@pytest.mark.parametrize("raw", [None, "", "Goalkeeper"])
async def test_both_player_stats_paths_retain_absence_instead_of_inventing_midfielder(raw):
    player = {"player": {"id": 42, "name": "Unknown role"},
              "statistics": [{"games": {"position": raw, "minutes": 90}}]}
    payload = {"errors": [], "response": [{"team": {"id": 10}, "players": [player]}]}
    for method,args in [("fetch_fixture_players", (123, 10)), ("fetch_all_fixture_players", (123,))]:
        result = await getattr(ProviderWithFakeClient(payload), method)(*args)
        assert result[0].position == (raw or "")
