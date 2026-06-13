"""
Repair missing GOAL and ASSIST events for players where name-matching failed.

For each (player, fixture) where player_stats.goals > matched GOAL events:
  - Creates synthetic GOAL events using M1 from existing STATS event, M2 from
    competition_stages, M3=1.0 (no minute available), M4=0.32, mvisit from home/away.
  - Recalculates sfa_season_scores for affected players.

Run: python repair_missing_goal_events.py
"""
from __future__ import annotations

import json
from collections import defaultdict

import psycopg2
import psycopg2.extras

DB = dict(host="localhost", port=5432, user="sfa", password="sfa", dbname="sfa")

# Base points per DB position value
GOAL_BASE: dict[str, int] = {
    "DEL": 500, "EXT": 500,
    "MC": 850,
    "DC": 1300, "LAT": 1300,
}
ASSIST_BASE: dict[str, int] = {
    "DEL": 500, "EXT": 500,
    "MC": 650,
    "DC": 950, "LAT": 950,
}

# M4ShotDifficulty(psxg=0.32) = 1.0 + (1.0 - 0.32) * 0.8 = 1.544
GOAL_M4   = round(1.0 + (1.0 - 0.32) * 0.8, 4)   # 1.544
ASSIST_M4 = 1.0                                     # psxg=None → 1.0


def combined(m1: float, m2: float, m3: float = 1.0, m4: float = 1.0, mvisit: float = 1.0) -> float:
    return max(0.3, min(4.0, m1 * m2 * m3 * m4 * mvisit))


def main() -> None:
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── Step 1: Find all (player, fixture) pairs where stats has more goals
    #           than the currently stored GOAL/GOAL_PENALTY events ────────────
    cur.execute("""
        SELECT
            ps.player_id,
            ps.fixture_id,
            ps.goals      AS stat_goals,
            ps.assists    AS stat_assists,
            COALESCE(ge.goal_count, 0)   AS event_goals,
            COALESCE(ae.assist_count, 0) AS event_assists,
            p.position,
            f.home_team_id,
            f.away_team_id,
            f.competition_id,
            f.season,
            f.stage,
            COALESCE(se.m1, 1.0)  AS m1,
            COALESCE(se.m2, 1.0)  AS m2
        FROM player_stats ps
        JOIN players p    ON p.id = ps.player_id
        JOIN fixtures f   ON f.id = ps.fixture_id
        -- goal events already matched
        LEFT JOIN (
            SELECT player_id, fixture_id, COUNT(*) AS goal_count
            FROM player_events
            WHERE event_type IN ('GOAL','GOAL_PENALTY','GOAL_SHOOTOUT')
            GROUP BY player_id, fixture_id
        ) ge ON ge.player_id = ps.player_id AND ge.fixture_id = ps.fixture_id
        -- assist events already matched
        LEFT JOIN (
            SELECT player_id, fixture_id, COUNT(*) AS assist_count
            FROM player_events
            WHERE event_type IN ('ASSIST','CORNER_ASSIST')
            GROUP BY player_id, fixture_id
        ) ae ON ae.player_id = ps.player_id AND ae.fixture_id = ps.fixture_id
        -- M1/M2 from the existing STATS event for this player+fixture
        LEFT JOIN (
            SELECT player_id, fixture_id, m1, m2
            FROM player_events
            WHERE event_type = 'STATS'
        ) se ON se.player_id = ps.player_id AND se.fixture_id = ps.fixture_id
        WHERE
            p.position NOT IN ('GK')
            AND (
                ps.goals   > COALESCE(ge.goal_count, 0)
                OR ps.assists > COALESCE(ae.assist_count, 0)
            )
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} (player, fixture) pairs with missing events\n")

    inserted_goals = 0
    inserted_assists = 0
    affected_player_comps: set[tuple[int, int, str]] = set()

    for row in rows:
        player_id   = row["player_id"]
        fixture_id  = row["fixture_id"]
        position    = row["position"]
        competition_id = row["competition_id"]
        season      = row["season"]
        is_away     = row["away_team_id"] and (
            # we need to know which team the player belongs to
            True  # resolved below
        )

        # Resolve is_away: get player's team_id and compare with fixture.away_team_id
        cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur2.execute("SELECT team_id FROM players WHERE id = %s", (player_id,))
        player_row = cur2.fetchone()
        if not player_row:
            continue
        team_id = player_row["team_id"]
        is_away = (team_id == row["away_team_id"])
        mvisit  = 1.05 if is_away else 1.0

        m1 = float(row["m1"])
        m2 = float(row["m2"])
        mvisit = 1.3 if is_away else 1.0

        # ── Insert missing GOAL events ────────────────────────────────────────
        missing_goals = row["stat_goals"] - row["event_goals"]
        if missing_goals > 0 and position in GOAL_BASE:
            base = GOAL_BASE[position]
            c = combined(m1, m2, 1.0, GOAL_M4, mvisit)
            pts = round(base * c, 2)

            for _ in range(missing_goals):
                cur2.execute("""
                    INSERT INTO player_events
                        (player_id, fixture_id, minute, event_type,
                         score_before, score_diff, psxg, m1, m2, m3, m4, mvisit, pts)
                    VALUES
                        (%s, %s, 75, 'GOAL',
                         NULL, NULL, 0.32, %s, %s, 1.0, %s, %s, %s)
                """, (player_id, fixture_id, m1, m2, GOAL_M4, mvisit, pts))
            inserted_goals += missing_goals
            affected_player_comps.add((player_id, competition_id, season))

        # ── Insert missing ASSIST events ──────────────────────────────────────
        missing_assists = row["stat_assists"] - row["event_assists"]
        if missing_assists > 0 and position in ASSIST_BASE:
            base = ASSIST_BASE[position]
            c = combined(m1, m2, 1.0, ASSIST_M4, mvisit)
            pts = round(base * c, 2)

            for _ in range(missing_assists):
                cur2.execute("""
                    INSERT INTO player_events
                        (player_id, fixture_id, minute, event_type,
                         score_before, score_diff, psxg, m1, m2, m3, m4, mvisit, pts)
                    VALUES
                        (%s, %s, 75, 'ASSIST',
                         NULL, NULL, NULL, %s, %s, 1.0, %s, %s, %s)
                """, (player_id, fixture_id, m1, m2, ASSIST_M4, mvisit, pts))
            inserted_assists += missing_assists
            affected_player_comps.add((player_id, competition_id, season))

    conn.commit()
    print(f"Inserted {inserted_goals} GOAL events, {inserted_assists} ASSIST events")
    print(f"Affected (player, competition) pairs: {len(affected_player_comps)}\n")

    # ── Step 2: Recalculate sfa_season_scores for affected players ────────────
    print("Recalculating season scores...")
    scores_updated = 0

    for (player_id, competition_id, season) in affected_player_comps:
        # Sum all events for this player in this competition+season
        cur.execute("""
            SELECT pe.event_type, pe.pts
            FROM player_events pe
            JOIN fixtures f ON f.id = pe.fixture_id
            WHERE pe.player_id = %s
              AND f.competition_id = %s
              AND f.season = %s
        """, (player_id, competition_id, season))
        all_events = cur.fetchall()
        if not all_events:
            continue

        new_total = round(sum(float(e["pts"]) for e in all_events), 2)

        # Rebuild breakdown
        breakdown: dict[str, dict] = {}
        for e in all_events:
            key = e["event_type"].lower()
            if key not in breakdown:
                breakdown[key] = {"count": 0, "pts": 0.0}
            breakdown[key]["count"] += 1
            breakdown[key]["pts"] = round(breakdown[key]["pts"] + float(e["pts"]), 2)

        # Add pct
        for key in breakdown:
            breakdown[key]["pct"] = (
                round(breakdown[key]["pts"] / new_total * 100, 1) if new_total > 0 else 0.0
            )

        # matches_played: count fixtures with ≥1 event
        cur.execute("""
            SELECT COUNT(DISTINCT pe.fixture_id)
            FROM player_events pe
            JOIN fixtures f ON f.id = pe.fixture_id
            WHERE pe.player_id = %s
              AND f.competition_id = %s
              AND f.season = %s
        """, (player_id, competition_id, season))
        matches_played = cur.fetchone()["count"]

        # Upsert season score
        cur.execute("""
            INSERT INTO sfa_season_scores
                (player_id, competition_id, season, total_pts, matches_played, breakdown, last_updated)
            VALUES
                (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT ON CONSTRAINT uq_sfa_season_score
            DO UPDATE SET
                total_pts = EXCLUDED.total_pts,
                breakdown = EXCLUDED.breakdown,
                last_updated = NOW()
        """, (player_id, competition_id, season, new_total, matches_played, json.dumps(breakdown)))

        scores_updated += 1

        if scores_updated % 200 == 0:
            conn.commit()
            print(f"  {scores_updated} scores updated...")

    conn.commit()
    print(f"Updated {scores_updated} season scores\n")
    print("Done. Run the ranking API to verify.")


if __name__ == "__main__":
    main()
