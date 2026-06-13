"""Try different header combinations to bypass Understat bot detection."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

import httpx

URL = "https://understat.com/league/La_liga/2024"

VARIANTS = [
    ("minimal", {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    }),
    ("with-accept", {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }),
    ("with-referer", {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://understat.com/",
        "Connection": "keep-alive",
    }),
]


async def main():
    for name, headers in VARIANTS:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30) as c:
            r = await c.get(URL)
        found = "playersData" in r.text
        print(f"{name:20s}: status={r.status_code} len={len(r.text):6d} playersData={found}")
        await asyncio.sleep(5)


asyncio.run(main())
