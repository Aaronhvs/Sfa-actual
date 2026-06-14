from sfa.domain.transfermarkt_ports import TM_POSITION_MAP
from sfa.infrastructure.models.enums import Position
import pytest

from sfa.infrastructure.providers.transfermarkt_scraper import (
    TransfermarktScraper,
    _POSITION_PATTERN,
)

MOCK_PROFILE_CENTRAL_MF = """
<html><body>
  <div class="data-header__label">
    Position:</span>
    <span class="data-header__content">Central Midfield</span>
  </div>
</body></html>
"""

MOCK_PROFILE_ATTACKING_MF = """
<html><body>
  <div class="data-header__label">
    Position:</span>
    <span class="data-header__content">Attacking Midfield</span>
  </div>
</body></html>
"""

MOCK_PROFILE_RIGHT_BACK = """
<html><body>
  <div class="data-header__label">
    Position:</span>
    <span class="data-header__content">Right-Back</span>
  </div>
</body></html>
"""


class TestTransfermarktPositionPattern:
    def test_parse_central_midfield(self):
        match = _POSITION_PATTERN.search(MOCK_PROFILE_CENTRAL_MF)
        assert match is not None
        assert match.group(1).strip() == "Central Midfield"

    def test_parse_attacking_midfield(self):
        match = _POSITION_PATTERN.search(MOCK_PROFILE_ATTACKING_MF)
        assert match is not None
        assert match.group(1).strip() == "Attacking Midfield"

    def test_parse_right_back(self):
        match = _POSITION_PATTERN.search(MOCK_PROFILE_RIGHT_BACK)
        assert match is not None
        assert match.group(1).strip() == "Right-Back"

    def test_no_match_on_empty_html(self):
        assert _POSITION_PATTERN.search("<html></html>") is None


class TestTmPositionMap:
    def test_attacking_midfield_maps_to_mco(self):
        assert TM_POSITION_MAP["Attacking Midfield"] == Position.MCO

    def test_central_midfield_maps_to_mc(self):
        assert TM_POSITION_MAP["Central Midfield"] == Position.MC

    def test_right_back_maps_to_lat(self):
        assert TM_POSITION_MAP["Right-Back"] == Position.LAT

    def test_centre_forward_maps_to_del(self):
        assert TM_POSITION_MAP["Centre-Forward"] == Position.DEL

    def test_mco_in_position_enum(self):
        assert Position.MCO == "MCO"

    def test_all_map_values_are_valid_position_enum(self):
        for key, value in TM_POSITION_MAP.items():
            assert isinstance(value, Position), f"Invalid Position for key {key!r}: {value!r}"


class StubTransfermarktScraper(TransfermarktScraper):
    def __init__(self, html: str | list[str]) -> None:
        self._html = html if isinstance(html, list) else [html]
        self.calls = 0

    async def _get_html(self, url: str) -> str | None:
        index = min(self.calls, len(self._html) - 1)
        self.calls += 1
        return self._html[index]


class TestTransfermarktSearch:
    @pytest.mark.anyio
    async def test_unique_name_fallback_accepts_national_team_context(self):
        html = """
        <a href="/hwang-in-beom/profil/spieler/2901">Hwang In-beom</a>
        <a href="/hwang-in-beom/profil/spieler/2901">Profile</a>
        """

        result = await StubTransfermarktScraper(html).search_player(
            "Hwang In-beom",
            "South Korea",
        )

        assert result is not None
        assert result.tm_id == 2901

    @pytest.mark.anyio
    async def test_name_fallback_rejects_ambiguous_results(self):
        html = """
        <a href="/alex-silva/profil/spieler/100">Alex Silva</a>
        <a href="/alex-silva/profil/spieler/200">Alex Silva</a>
        """

        result = await StubTransfermarktScraper(html).search_player(
            "Alex Silva",
            "Brazil",
        )

        assert result is None

    @pytest.mark.anyio
    async def test_retries_two_part_name_in_reverse_order(self):
        scraper = StubTransfermarktScraper([
            "<html></html>",
            '<a href="/in-beom-hwang/profil/spieler/365394">In-beom Hwang</a>',
        ])

        result = await scraper.search_player("Hwang In-beom", "South Korea")

        assert result is not None
        assert result.tm_id == 365394
        assert scraper.calls == 2
