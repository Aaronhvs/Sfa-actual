from __future__ import annotations

from sfa.infrastructure.providers.national_team_elo_provider import (
    NationalTeamEloProvider,
    parse_eloratings_tsv,
    parse_national_team_elo,
)


def test_parse_national_team_elo_from_html_sample() -> None:
    html = """
    <html>
      <body>
        <h1>World Football Elo Ratings</h1>
        <p>Ratings and Statistics as of Tue Jun 16 2026</p>
        <table>
          <tr><td>1.</td><td>Spain</td><td>2129</td></tr>
          <tr><td>2.</td><td>Argentina</td><td>2108</td></tr>
          <tr><td>3.</td><td>Brazil</td><td>2099</td></tr>
        </table>
      </body>
    </html>
    """

    entries = parse_national_team_elo(html)

    assert [entry.country_name for entry in entries[:3]] == ["Spain", "Argentina", "Brazil"]
    assert entries[0].rank == 1
    assert entries[0].elo_raw == 2129
    assert entries[0].source_date == "Tue Jun 16 2026"


def test_parse_eloratings_tsv_uses_team_dictionary() -> None:
    world_cup_tsv = "\n".join([
        "1\t1\tES\t2129\t1\t2189",
        "2\t2\tAR\t2115\t1\t2172",
        "3\t7\tBR\t1978\t1\t2195",
    ])
    teams_tsv = "\n".join([
        "AR\tArgentina",
        "BR\tBrazil",
        "ES\tSpain",
    ])

    entries = parse_eloratings_tsv(world_cup_tsv, teams_tsv, "Wed Jun 17 2026")

    assert [entry.country_name for entry in entries] == ["Spain", "Argentina", "Brazil"]
    assert entries[0].rank == 1
    assert entries[0].elo_raw == 2129.0
    assert entries[0].source_date == "Wed Jun 17 2026"


def test_resolve_team_name_uses_explicit_mapping() -> None:
    provider = NationalTeamEloProvider()

    resolved = provider.resolve_team_name("United States", ["USA", "Brazil"])

    assert resolved == "USA"


def test_resolve_team_name_uses_fuzzy_fallback() -> None:
    provider = NationalTeamEloProvider()

    resolved = provider.resolve_team_name("Korea Rep", ["South Korea", "Japan"])

    assert resolved == "South Korea"
