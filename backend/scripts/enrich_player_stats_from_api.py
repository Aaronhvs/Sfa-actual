"""
Enrich player goals/assists in sfa_season_scores from API-Football /players endpoint.

Useful when fixture-level events missed goal/assist data (e.g. Vinicius 2025).
Fetches aggregate stats per player+season and injects them into the breakdown JSON
and updates the ranking display fields.

Usage:
    # Fix a specific player by external_id
    docker exec backend-api-1 python3 scripts/enrich_player_stats_from_api.py --player-id 762 --season 2025

    # Fix all players with missing goals in a competition
    docker exec backend-api-1 python3 scripts/enrich_player_stats_from_api.py --competition "La Liga" --season 2025 --only-missing

    # Dry-run (no DB changes)
    docker exec backend-api-1 python3 scripts/enrich_player_stats_from_api.py --player-id 762 --season 2025 --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time

import httpx
from sqlalchemy import select, text

sys.path.insert(0, "src")

from sfa.core.config import get_settings  # noqa: E402
from sfa.infrastructure.database import AsyncSessionLocal  # noqa: E402
from sfa.infrastructure.models.players.models import Player  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def fetch_player_stats(
    client: httpx.AsyncClient, api_key: str, base_url: str, external_id: int, season: int
) -> dict | None:
    """Call /players?id=X&season=Y and return the stats dict."""
    headers = {"x-apisports-key": api_key}
    url = f"{base_url}/players"
    params = {"id": external_id, "season": season}

    resp = await client.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("response", [])
    if not results:
        return None

    # API returns one entry per player+team+league combo; aggregate across all
    total_goals = 0
    total_assists = 0
    total_penalty_goals = 0

    for entry in results:
        stats_list = entry.get("statistics", [])
        for stat in stats_list:
            goals = stat.get("goals", {}) or {}
            total_goals += goals.get("total") or 0
            total_assists += goals.get("assists") or 0
            total_penalty_goals += goals.get("conceded") or 0  # penalty scored in "penaltys.scored"

            penalties = stat.get("penalty", {}) or {}
            # penalty.scored is the correct field for penalties scored
            pen_scored = penalties.get("scored") or 0
            total_penalty_goals_correct = pen_scored

    # Re-aggregate correctly
    total_goals = 0
    total_assists = 0
    total_penalty_goals = 0

    for entry in results:
        for stat in entry.get("statistics", []):
            g = stat.get("goals", {}) or {}
            p = stat.get("penalty", {}) or {}
            total_goals += g.get("total") or 0
            total_assists += g.get("assists") or 0
            total_penalty_goals += p.get("scored") or 0

    return {
        "goals": total_goals,
        "assists": total_assists,
        "penalty_goals": total_penalty_goals,
    }


async def get_players_missing_goals(session, competition_name: str, season: str) -> list[dict]:
    """Return players in a competition+season that have no goal events in breakdown."""
    rows = await session.execute(
        text("""
            SELECT p.id, p.external_id, p.name, s.id as score_id,
                   s.competition_id, s.breakdown, s.total_pts
            FROM sfa_season_scores s
            JOIN players p ON p.id = s.player_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE c.name = :comp AND s.season = :season AND s.rules_version_id = 3
              AND (s.breakdown->>'goal' IS NULL OR (s.breakdown->>'goal')::jsonb->>'count' = '0')
            ORDER BY s.total_pts DESC
        """),
        {"comp": competition_name, "season": season},
    )
    return [dict(r._mapping) for r in rows.fetchall()]


async def update_breakdown_with_api_stats(
    session,
    score_id: int,
    current_breakdown: dict,
    api_stats: dict,
    player_name: str,
    dry_run: bool,
) -> bool:
    """Inject goals/assists from API into the breakdown JSON."""
    goals = api_stats["goals"]
    assists = api_stats["assists"]
    penalty_goals = api_stats["penalty_goals"]

    non_penalty_goals = goals - penalty_goals
    if non_penalty_goals < 0:
        non_penalty_goals = 0

    if goals == 0 and assists == 0:
        logger.info("  %s: API returned 0 goals, 0 assists — skipping", player_name)
        return False

    new_breakdown = dict(current_breakdown)

    # Inject goal count (pts=0 — we're only fixing the display count, not re-scoring)
    if non_penalty_goals > 0:
        existing = new_breakdown.get("goal", {})
        new_breakdown["goal"] = {
            "pts": existing.get("pts", 0.0),
            "count": non_penalty_goals,
            "pct": existing.get("pct", 0.0),
            "_source": "api_football_enrich",
        }

    if penalty_goals > 0:
        existing = new_breakdown.get("goal_penalty", {})
        new_breakdown["goal_penalty"] = {
            "pts": existing.get("pts", 0.0),
            "count": penalty_goals,
            "pct": existing.get("pct", 0.0),
            "_source": "api_football_enrich",
        }

    if assists > 0:
        existing = new_breakdown.get("assist", {})
        new_breakdown["assist"] = {
            "pts": existing.get("pts", 0.0),
            "count": assists,
            "pct": existing.get("pct", 0.0),
            "_source": "api_football_enrich",
        }

    logger.info(
        "  %s: goals=%d (pen=%d) assists=%d",
        player_name, goals, penalty_goals, assists,
    )

    if dry_run:
        logger.info("  [DRY RUN] Would update score_id=%d breakdown", score_id)
        return True

    await session.execute(
        text("UPDATE sfa_season_scores SET breakdown = :bd WHERE id = :sid"),
        {"bd": json.dumps(new_breakdown), "sid": score_id},
    )
    return True


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    api_key = settings.API_FOOTBALL_KEY
    base_url = settings.API_FOOTBALL_BASE_URL

    async with httpx.AsyncClient(timeout=30) as client:
        async with AsyncSessionLocal() as session:
            if args.player_id:
                # Single player mode
                row = await session.execute(
                    select(Player).where(Player.external_id == args.player_id)
                )
                player = row.scalar_one_or_none()
                if player is None:
                    logger.error("Player with external_id=%d not found", args.player_id)
                    return

                logger.info("Fetching stats for %s (ext_id=%d, season=%d)...", player.name, args.player_id, args.season)
                api_stats = await fetch_player_stats(client, api_key, base_url, args.player_id, args.season)
                if api_stats is None:
                    logger.error("No stats returned from API")
                    return

                logger.info("API stats: %s", api_stats)

                # Update all score rows for this player+season
                rows = await session.execute(
                    text("""
                        SELECT id, competition_id, breakdown, total_pts
                        FROM sfa_season_scores
                        WHERE player_id = :pid AND season = :season AND rules_version_id = 3
                        ORDER BY total_pts DESC
                    """),
                    {"pid": player.id, "season": str(args.season)},
                )
                score_rows = rows.fetchall()

                if not score_rows:
                    logger.error("No sfa_season_scores rows found for player_id=%d season=%s", player.id, args.season)
                    return

                # Update only the top competition row (highest pts) to avoid duplicating goals across comps
                top_row = score_rows[0]
                bd = top_row.breakdown if isinstance(top_row.breakdown, dict) else json.loads(top_row.breakdown)
                changed = await update_breakdown_with_api_stats(
                    session, top_row.id, bd, api_stats, player.name, args.dry_run
                )

                if changed and not args.dry_run:
                    await session.commit()
                    logger.info("Committed changes for %s", player.name)

            elif args.competition and args.only_missing:
                # Batch mode for all players missing goals in a competition
                players = await get_players_missing_goals(session, args.competition, str(args.season))
                logger.info(
                    "Found %d players missing goals in %s %s",
                    len(players), args.competition, args.season,
                )

                updated = 0
                for i, p in enumerate(players):
                    if p["external_id"] is None:
                        continue

                    if i > 0 and i % 5 == 0:
                        time.sleep(1)  # rate limit: ~5 req/s

                    try:
                        api_stats = await fetch_player_stats(
                            client, api_key, base_url, p["external_id"], args.season
                        )
                    except Exception as exc:
                        logger.warning("Error fetching %s: %s", p["name"], exc)
                        continue

                    if api_stats is None or (api_stats["goals"] == 0 and api_stats["assists"] == 0):
                        continue

                    bd = p["breakdown"] if isinstance(p["breakdown"], dict) else json.loads(p["breakdown"] or "{}")
                    changed = await update_breakdown_with_api_stats(
                        session, p["score_id"], bd, api_stats, p["name"], args.dry_run
                    )
                    if changed:
                        updated += 1

                if not args.dry_run and updated > 0:
                    await session.commit()
                    logger.info("Committed %d player updates", updated)
                else:
                    logger.info("Updated (dry-run): %d", updated)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich player goals/assists from API-Football")
    parser.add_argument("--player-id", type=int, help="API-Football external_id of the player")
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g. 2025)")
    parser.add_argument("--competition", help="Competition name (for batch mode)")
    parser.add_argument("--only-missing", action="store_true", help="Only update players with 0 goals")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, no DB writes")
    args = parser.parse_args()

    if not args.player_id and not (args.competition and args.only_missing):
        parser.error("Provide --player-id OR --competition + --only-missing")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
