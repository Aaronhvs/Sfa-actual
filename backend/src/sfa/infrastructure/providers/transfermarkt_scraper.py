from __future__ import annotations

import logging
import re
import urllib.parse

import httpx

from sfa.domain.transfermarkt_ports import TM_POSITION_MAP, TmPlayerData, TmSearchResult

logger = logging.getLogger(__name__)

_TM_BASE = "https://www.transfermarkt.com"

_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

_POSITION_PATTERN = re.compile(
    r'Position:\s*(?:</span>\s*)?<span[^>]*class="[^"]*data-header__content[^"]*"[^>]*>'
    r'\s*([^<]+?)\s*</span>',
    re.IGNORECASE | re.DOTALL,
)
_PROFILE_HREF_PATTERN = re.compile(r'/([^/]+)/profil/spieler/(\d+)')


class TransfermarktScraper:
    async def _get_html(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    logger.warning("[TransfermarktScraper] 404 for %s", url)
                    return None
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as exc:
            logger.warning("[TransfermarktScraper] HTTP error for %s: %s", url, exc)
            return None
        except httpx.RequestError as exc:
            logger.warning("[TransfermarktScraper] Request error for %s: %s", url, exc)
            return None

    async def fetch_player_position(self, tm_id: int, slug: str) -> TmPlayerData | None:
        url = f"{_TM_BASE}/{slug}/profil/spieler/{tm_id}"
        html = await self._get_html(url)
        if not html:
            return None

        match = _POSITION_PATTERN.search(html)
        if match is None:
            logger.warning("[TransfermarktScraper] Position not found for tm_id=%s", tm_id)
            return None

        position_raw = match.group(1).strip()
        position_mapped = TM_POSITION_MAP.get(position_raw)
        if position_mapped is None:
            logger.warning("[TransfermarktScraper] Unknown position %r for tm_id=%s", position_raw, tm_id)
            return None

        return TmPlayerData(
            tm_id=tm_id,
            position_raw=position_raw,
            position_mapped=position_mapped,
        )

    async def search_player(self, name: str, team_name: str) -> TmSearchResult | None:
        encoded = urllib.parse.quote(name)
        url = f"{_TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={encoded}"
        html = await self._get_html(url)
        if not html:
            return None

        team_name_lower = team_name.lower()
        team_parts = [part for part in team_name_lower.split() if len(part) > 2]
        for match in _PROFILE_HREF_PATTERN.finditer(html):
            slug = match.group(1)
            tm_id = int(match.group(2))
            start = max(0, match.start() - 300)
            end = min(len(html), match.end() + 300)
            context = html[start:end].lower()
            if team_name_lower in context or any(part in context for part in team_parts):
                return TmSearchResult(tm_id=tm_id, name=name, team_name=team_name, slug=slug)

        logger.info("[TransfermarktScraper] No match for %s (%s)", name, team_name)
        return None
