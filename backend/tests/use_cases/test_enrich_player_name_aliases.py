from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.enrich_player_name_aliases import EnrichPlayerNameAliasesUseCase
from sfa.domain.player_name_aliases import PlayerNameAliasRepositoryProtocol, PlayerNameProfileDTO, normalize_search_name


class FakeAliases(PlayerNameAliasRepositoryProtocol):
    def __init__(self):
        self.identities = {568001: 1022093, 42: 2}
        self.rows = {}

    async def find_player_id(self, external_id):
        return self.identities.get(external_id)

    async def add_aliases(self, player_id, external_id, aliases, *, provider, source_ref, captured_at):
        added = 0
        for alias in aliases:
            key = player_id, provider, normalize_search_name(alias)
            if key not in self.rows:
                self.rows[key] = (alias, external_id, source_ref, captured_at)
                added += 1
        return added


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


@pytest.mark.anyio
async def test_reviewed_public_name_survives_abbreviated_null_reingestion_and_homonyms():
    repo = FakeAliases()
    uc = EnrichPlayerNameAliasesUseCase(repo)
    reviewed = await uc.execute((PlayerNameProfileDTO(568001, full_name="Xavi Espart"),),
        provider="official-club-reviewed", source_ref="https://club.example/players/568001;actor=reviewer", captured_at=NOW)
    assert reviewed.aliases_added == 1
    for _ in range(2):
        await uc.execute((PlayerNameProfileDTO(568001, "X. Espart"), PlayerNameProfileDTO(42, "Xavi Espart")),
            provider="api-football", source_ref="players?season=2026", captured_at=NOW)
    assert len(repo.rows) == 3
    assert (1022093, "official-club-reviewed", "xavi espart") in repo.rows
    assert repo.identities[42] != repo.identities[568001]


@pytest.mark.anyio
async def test_empty_and_unknown_profiles_never_create_players():
    repo = FakeAliases()
    uc = EnrichPlayerNameAliasesUseCase(repo)
    result = await uc.execute((), provider="api-football", source_ref="cache", captured_at=NOW)
    assert result.profiles == result.aliases_added == 0
    result = await uc.execute((PlayerNameProfileDTO(99, "Other"), PlayerNameProfileDTO(42)),
        provider="api-football", source_ref="cache", captured_at=NOW)
    assert result.unknown_external_ids == (99,)
    assert not repo.rows


@pytest.mark.anyio
@pytest.mark.parametrize("profile,provider,source,at", [
    (PlayerNameProfileDTO(True), "api", "cache", NOW),
    (PlayerNameProfileDTO(-1), "api", "cache", NOW),
    (PlayerNameProfileDTO(42), "", "cache", NOW),
    (PlayerNameProfileDTO(42), "a" * 81, "cache", NOW),
    (PlayerNameProfileDTO(42), "api", "", NOW),
    (PlayerNameProfileDTO(42), "api", "cache", datetime(2026, 1, 1)),
])
async def test_rejects_missing_provenance_or_invalid_identity(profile, provider, source, at):
    with pytest.raises(ValueError):
        await EnrichPlayerNameAliasesUseCase(FakeAliases()).execute((profile,), provider=provider, source_ref=source, captured_at=at)


def test_names_normalize_accents_initials_punctuation_and_spaces_without_guessing():
    assert normalize_search_name("  X.  Éspart ") == "x espart"
    assert PlayerNameProfileDTO(42, "X. Espart").aliases() == ("X. Espart",)
    assert PlayerNameProfileDTO(42, "Xavi Espart", "Xavi", "Espart", " Xavi   Espart ").aliases() == ("Xavi Espart",)
    assert PlayerNameProfileDTO(42, first_name="Xavi").aliases() == ()
    with pytest.raises(ValueError):
        PlayerNameProfileDTO(42, full_name="a" * 251).aliases()
