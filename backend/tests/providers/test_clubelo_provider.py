from __future__ import annotations

from datetime import date

import pytest

from sfa.infrastructure.providers.clubelo_provider import ClubEloProvider, _parse_csv


@pytest.mark.parametrize(
    "source_name, sfa_name",
    [
        ("Bayern", "Bayern München"),
        ("Koeln", "1. FC Köln"),
        ("Roma", "AS Roma"),
        ("PSV", "PSV Eindhoven"),
        ("Union SG", "Union St. Gilloise"),
        ("Alkmaar", "AZ Alkmaar"),
        ("Arda", "Arda Kardzhali"),
        ("Forest", "Nottingham Forest"),
        ("Gijon", "Sporting Gijon"),
        ("Karabakh Agdam", "Qarabag"),
        ("Leonesa", "Cultural Leonesa"),
        ("Polissya Zhytomyr", "Polessya"),
        ("Rakow", "Rak\u00f3w Cz\u0119stochowa"),
        ("Razgrad", "Ludogorets"),
        ("RFS", "R\u012bgas FS"),
        ("Sheffield Weds", "Sheffield Wednesday"),
        ("St Gillis", "Union St. Gilloise"),
        ("Steaua", "FCSB"),
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


def test_parse_csv_preserves_authoritative_validity_interval() -> None:
    rows = _parse_csv(
        "Rank,Club,Country,Level,Elo,From,To\n"
        "1,Cardiff,ENG,2,1434.11,2025-05-29,2025-07-05\n"
    )

    assert len(rows) == 1
    assert rows[0].valid_from == date(2025, 5, 29)
    assert rows[0].valid_to == date(2025, 7, 5)


def test_history_identity_requires_verified_clubelo_identifier_and_country() -> None:
    identity = ClubEloProvider().get_history_identity("SSV Jahn Regensburg")

    assert identity is not None
    assert identity.clubelo_identifier == "Regensburg"
    assert identity.expected_country == "GER"
    assert ClubEloProvider().get_history_identity("Lincoln") is None
