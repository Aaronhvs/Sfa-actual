"""
Backfill player photos from Wikipedia.
For each player: try Wikipedia → fall back to existing API-Football URL.
Run: python backfill_wikipedia_photos.py
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

import psycopg2

DB = dict(host="localhost", port=5432, user="sfa", password="sfa", dbname="sfa")
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
HEADERS = {"User-Agent": "SFA-project/1.0 (football stats app; contact: admin@sfa.com)"}
DELAY = 0.45  # seconds between requests (~2 req/s — well within Wikipedia limits)
THUMB_SIZE = 500  # px — replace default thumbnail size in Wikimedia URLs


@dataclass
class PlayerRow:
    id: int
    name: str
    photo_url: str | None


def bump_thumb_size(url: str, size: int) -> str:
    """Replace the NNNpx- part in a Wikimedia thumbnail URL to get a larger image."""
    import re
    return re.sub(r"/\d+px-", f"/{size}px-", url)


def fetch_wikipedia_image(name: str) -> str | None:
    """Return thumbnail URL from Wikipedia for the given name, or None."""
    candidates = [
        name,
        f"{name} (footballer)",
        f"{name} (soccer)",
    ]
    for candidate in candidates:
        encoded = urllib.parse.quote(candidate)
        url = WIKI_SUMMARY.format(encoded)
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read())
            # Only accept pages that are likely about a person (not disambiguation)
            if data.get("type") in ("disambiguation", "https://mediawiki.org/wiki/Help:Disambiguation"):
                continue
            thumb = data.get("thumbnail", {}).get("source")
            if thumb and "upload.wikimedia.org" in thumb:
                return bump_thumb_size(thumb, THUMB_SIZE)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue  # try next candidate
            print(f"  HTTP {e.code} for '{candidate}'")
        except Exception as e:
            print(f"  Error for '{candidate}': {e}")
    return None


def main() -> None:
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    # Fetch all players ordered by total_pts DESC so the most visible get done first
    cur.execute("""
        SELECT p.id, p.name, p.photo_url
        FROM players p
        LEFT JOIN sfa_season_scores s ON s.player_id = p.id
        GROUP BY p.id, p.name, p.photo_url
        ORDER BY MAX(s.total_pts) DESC NULLS LAST
    """)
    players = [PlayerRow(id=r[0], name=r[1], photo_url=r[2]) for r in cur.fetchall()]

    total = len(players)
    updated = 0
    kept = 0
    failed = 0

    print(f"Processing {total} players...\n")

    for i, player in enumerate(players, 1):
        wiki_url = fetch_wikipedia_image(player.name)

        if wiki_url:
            cur.execute(
                "UPDATE players SET photo_url = %s WHERE id = %s",
                (wiki_url, player.id),
            )
            updated += 1
            status = "WIKI"
        elif player.photo_url:
            kept += 1
            status = "API "
        else:
            failed += 1
            status = "NONE"

        if i % 50 == 0 or i <= 20:
            print(f"[{i:4}/{total}] {status} | {player.name}")

        if i % 200 == 0:
            conn.commit()
            print(f"  -- committed at {i} --")

        time.sleep(DELAY)

    conn.commit()
    conn.close()

    print(f"\nDone.")
    print(f"  Wikipedia: {updated}")
    print(f"  Kept API-Football: {kept}")
    print(f"  No photo: {failed}")


if __name__ == "__main__":
    main()
