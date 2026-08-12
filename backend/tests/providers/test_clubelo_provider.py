from __future__ import annotations

import pytest

from sfa.infrastructure.providers.clubelo_provider import ClubEloProvider


@pytest.mark.parametrize(
    "source_name, sfa_name",
    [
        ("Bayern", "Bayern München"),
        ("Koeln", "1. FC Köln"),
        ("Roma", "AS Roma"),
        ("PSV", "PSV Eindhoven"),
        ("Union SG", "Union St. Gilloise"),
        ("Alkmaar", "AZ Alkmaar"),
        ("Karabakh Agdam", "Qarabag"),
        ("RFS", "R\u012bgas FS"),
        ("Sheffield Weds", "Sheffield Wednesday"),
        ("St Gillis", "Union St. Gilloise"),
        ("Wolfsburg", "VfL Wolfsburg"),
        ("Zrinjski Mostar", "Zrinjski"),
    ],
)
def test_resolve_team_name_uses_current_sfa_aliases(
    source_name: str,
    sfa_name: str,
) -> None:
    assert ClubEloProvider().resolve_team_name(source_name, [sfa_name]) == sfa_name


def test_resolve_team_name_falls_back_to_original_when_legacy_alias_is_absent() -> None:
    provider = ClubEloProvider()

    assert provider.resolve_team_name("Alaves", ["Alaves"]) == "Alaves"
    assert provider.resolve_team_name("Brighton", ["Brighton"]) == "Brighton"


def test_resolve_team_name_normalizes_accents_and_club_tokens() -> None:
    provider = ClubEloProvider()

    assert provider.resolve_team_name("Fortuna Dusseldorf", ["Fortuna Düsseldorf"]) == (
        "Fortuna Düsseldorf"
    )
    assert provider.resolve_team_name("Basel", ["FC Basel 1893"]) == "FC Basel 1893"


def test_resolve_team_name_does_not_guess_ambiguous_core_name() -> None:
    provider = ClubEloProvider()

    assert provider.resolve_team_name("United", ["FC United", "SC United"]) is None


@pytest.mark.parametrize(
    "source_name, unrelated_sfa_name",
    [
        ("Torino", "Antoniano"),
        ("Bayern", "Bayeux"),
        ("Atletico", "Atl\u00e8tic Lleida"),
        ("Nottingham", "Dinamo Brest"),
    ],
)
def test_resolve_team_name_rejects_superficial_similarity(
    source_name: str,
    unrelated_sfa_name: str,
) -> None:
    assert ClubEloProvider().resolve_team_name(source_name, [unrelated_sfa_name]) is None
