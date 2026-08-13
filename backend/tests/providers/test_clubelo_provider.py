from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest

from sfa.domain.scoring_ports import ClubEloSourceDTO
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


@pytest.mark.anyio
async def test_snapshot_falls_back_to_previous_available_date(monkeypatch) -> None:
    provider = ClubEloProvider()
    attempts: list[str] = []
    previous = ClubEloSourceDTO(
        source_reference="http://api.clubelo.com/2025-07-06",
        fetched_at=datetime(2025, 7, 7, tzinfo=timezone.utc),
        payload_sha256="a" * 64,
        ratings=tuple(_parse_csv(
            "Rank,Club,Country,Level,Elo,From,To\n"
            "1,Liverpool,ENG,1,1993.43,2025-05-29,2025-08-15\n"
        )),
    )

    async def fake_fetch(path: str):
        attempts.append(path)
        if path == "2025-07-07":
            request = httpx.Request("GET", f"http://api.clubelo.com/{path}")
            response = httpx.Response(502, request=request)
            raise httpx.HTTPStatusError("bad gateway", request=request, response=response)
        return previous

    monkeypatch.setattr(provider, "_fetch_source", fake_fetch)

    result = await provider.fetch_snapshot("2025-07-07")

    assert attempts == ["2025-07-07", "2025-07-06"]
    assert result.source_reference.endswith("2025-07-06")
