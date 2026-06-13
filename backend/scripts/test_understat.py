"""Debug Understat response."""
import asyncio
import sys
import re
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

async def main():
    url = "https://understat.com/league/La_liga/2024"
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type', 'unknown')}")
    html = resp.text
    print(f"HTML length: {len(html)}")

    # Check if playersData exists
    if "playersData" in html:
        print("playersData FOUND in HTML")
        pattern = r"var\s+playersData\s*=\s*JSON\.parse\('(.+?)'\)"
        match = re.search(pattern, html, re.DOTALL)
        if match:
            print(f"Pattern matched! JSON length: {len(match.group(1))}")
        else:
            print("Pattern NOT matched - HTML snippet around playersData:")
            idx = html.find("playersData")
            print(repr(html[max(0,idx-50):idx+200]))
    else:
        print("playersData NOT in HTML")
        print("First 500 chars of HTML:")
        print(repr(html[:500]))

asyncio.run(main())
