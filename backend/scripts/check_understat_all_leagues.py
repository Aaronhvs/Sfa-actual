"""Check if Understat is serving playersData for all leagues."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

LEAGUES = [
    ("La Liga", "La_liga"),
    ("Premier League", "EPL"),
    ("Bundesliga", "Bundesliga"),
    ("Serie A", "Serie_A"),
    ("Ligue 1", "Ligue_1"),
]


async def check(name: str, slug: str) -> None:
    url = f"https://understat.com/league/{slug}/2024"
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as c:
        r = await c.get(url)
    found = "playersData" in r.text
    print(f"{name:20s}: status={r.status_code} len={len(r.text):6d} playersData={found}")
    await asyncio.sleep(3)


async def main():
    for name, slug in LEAGUES:
        await check(name, slug)


asyncio.run(main())
