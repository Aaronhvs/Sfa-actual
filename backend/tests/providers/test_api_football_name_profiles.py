import pytest

from sfa.infrastructure.providers.api_football import APIFootballProvider


class FakeNameProvider(APIFootballProvider):
    def __init__(self, response):
        self.response, self.calls = response, []

    async def _get(self, endpoint, params=None):
        self.calls.append((endpoint, params))
        return self.response


def test_parser_retains_available_fields_and_never_expands_initials():
    parser = APIFootballProvider.parse_player_name_profile
    profile = parser({"player": {"id": 568001, "name": "X. Espart", "firstname": None, "lastname": None}})
    assert profile.aliases() == ("X. Espart",)
    profile = parser({"player": {"id": 42, "name": "F. Lopez", "firstname": "Fermín", "lastname": "López", "full_name": 12}})
    assert profile.aliases() == ("F. Lopez", "Fermín López")
    for entry in ({}, {"player": {"id": True}}, {"player": {"id": -1}}):
        assert parser(entry) is None


@pytest.mark.anyio
async def test_player_profile_checks_identity_and_team_pages_are_explicit():
    provider = FakeNameProvider({"paging": {"current": 2, "total": 3}, "response": [
        {"player": {"id": 42, "name": "Other"}}, {"player": {"id": 568001, "name": "X. Espart"}}, {}]})
    assert (await provider.fetch_player_name_profile(568001, 2026)).external_id == 568001
    assert await provider.fetch_player_name_profile(100, 2026) is None
    page = await provider.fetch_team_name_profiles(529, 2026, 2)
    assert (page.page, page.total_pages, len(page.profiles)) == (2, 3, 2)
    assert provider.calls[-1] == ("players", {"team": 529, "season": 2026, "page": 2})


@pytest.mark.anyio
@pytest.mark.parametrize("paging", [{"current": 1, "total": 2}, {"current": 2, "total": 1}, {"current": True}, {"current": 2, "total": 1001}])
async def test_unexpected_pagination_is_not_silently_skipped(paging):
    with pytest.raises(ValueError):
        await FakeNameProvider({"paging": paging}).fetch_team_name_profiles(529, 2026, 2)
