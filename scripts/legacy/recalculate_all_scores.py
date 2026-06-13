"""
Full recalculation of all player_events and sfa_season_scores.
Applies:
  1. New M2 values from competition_stages (was always 1.0 before).
  2. Reduced DUELS_WON base pts (FW:30, MF:40, DF:50).

Run: python recalculate_all_scores.py
"""
from __future__ import annotations

import json
from collections import defaultdict

import psycopg2
import psycopg2.extras

DB = dict(host="localhost", port=5432, user="sfa", password="sfa", dbname="sfa")

# ── Base points (must match services.py) ────────────────────────────────────

GOAL_BASE: dict[str, dict[str, int]] = {
    "FW": {"GOAL": 500, "GOAL_PENALTY": 300, "GOAL_SHOOTOUT": 300,
            "ASSIST": 500, "CORNER_ASSIST": 250},
    "MF": {"GOAL": 850, "GOAL_PENALTY": 450, "GOAL_SHOOTOUT": 450,
            "ASSIST": 650, "CORNER_ASSIST": 350},
    "DF": {"GOAL": 1300, "GOAL_PENALTY": 500, "GOAL_SHOOTOUT": 500,
            "ASSIST": 950, "CORNER_ASSIST": 450},
}

STATS_BASE: dict[str, dict[str, int]] = {
    "FW": {"duels_won": 30,  "tackles_won": 180, "interceptions": 0,
           "blocks": 150, "dribbles_won": 100, "passes_key": 150,
           "shots_on": 70,  "fouls_drawn": 50,  "clearances": 0},
    "MF": {"duels_won": 40,  "tackles_won": 140, "interceptions": 0,
           "blocks": 100, "dribbles_won": 180, "passes_key": 120,
           "shots_on": 50,  "fouls_drawn": 35,  "clearances": 20},
    "DF": {"duels_won": 50,  "tackles_won": 100, "interceptions": 0,
           "blocks": 70,  "dribbles_won": 280, "passes_key": 180,
           "shots_on": 30,  "fouls_drawn": 20,  "clearances": 25},
}

POS_GROUP: dict[str, str] = {
    "DEL": "FW", "EXT": "FW",
    "MC": "MF",
    "DC": "DF", "LAT": "DF",
}

GOAL_EVENT_TYPES = {"GOAL", "GOAL_PENALTY", "GOAL_SHOOTOUT", "ASSIST", "CORNER_ASSIST"}


def clamped(m1: float, m2: float, m3: float, m4: float, mvisit: float) -> float:
    return max(0.3, min(4.0, m1 * m2 * m3 * m4 * mvisit))


def main() -> None:
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── 1. Load stage factor lookup ──────────────────────────────────────────
    cur.execute("SELECT competition_id, stage, stage_factor FROM competition_stages")
    stage_factors: dict[tuple[int, str], float] = {
        (r["competition_id"], r["stage"]): float(r["stage_factor"])
        for r in cur.fetchall()
    }
    print(f"Loaded {len(stage_factors)} stage factors")

    # ── 2. Update M2 on every player_event ──────────────────────────────────
    cur.execute("""
        SELECT pe.id, pe.event_type, pe.m1, pe.m2, pe.m3, pe.m4, pe.mvisit, pe.pts,
               pe.player_id, pe.fixture_id,
               f.competition_id, f.stage,
               p.position
        FROM player_events pe
        JOIN fixtures f ON f.id = pe.fixture_id
        JOIN players p  ON p.id = pe.player_id
    """)
    events = cur.fetchall()
    print(f"Loaded {len(events)} events to recalculate")

    # Load player_stats for STATS events
    cur.execute("""
        SELECT player_id, fixture_id,
               goals, assists, shots_on, passes_key,
               dribbles_won, duels_won, tackles_won, interceptions,
               blocks, fouls_drawn, clearances
        FROM player_stats
    """)
    stats_map: dict[tuple[int, int], dict] = {
        (r["player_id"], r["fixture_id"]): dict(r)
        for r in cur.fetchall()
    }
    print(f"Loaded {len(stats_map)} player_stats rows")

    updated = 0
    skipped = 0

    for ev in events:
        pos = ev["position"]
        group = POS_GROUP.get(pos)
        if group is None:  # GK
            skipped += 1
            continue

        comp_id = ev["competition_id"]
        stage   = ev["stage"]
        new_m2  = stage_factors.get((comp_id, stage), 1.0)
        m1      = float(ev["m1"])
        m3      = float(ev["m3"])
        m4      = float(ev["m4"])
        mvisit  = float(ev["mvisit"])
        evt     = ev["event_type"]

        if evt in GOAL_EVENT_TYPES:
            base = float(GOAL_BASE[group].get(evt, 0))
            if base == 0:
                skipped += 1
                continue
            new_pts = round(base * clamped(m1, new_m2, m3, m4, mvisit), 2)

        elif evt == "STATS":
            ps = stats_map.get((ev["player_id"], ev["fixture_id"]))
            if ps is None:
                skipped += 1
                continue

            sb = STATS_BASE[group]
            goals   = ps["goals"] or 0
            assists = ps["assists"] or 0

            stat_counts = {
                "duels_won":    ps["duels_won"] or 0,
                "tackles_won":  (ps["tackles_won"] or 0) + (ps["interceptions"] or 0),
                "blocks":       ps["blocks"] or 0,
                "dribbles_won": ps["dribbles_won"] or 0,
                "passes_key":   max(0, (ps["passes_key"] or 0) - assists),
                "shots_on":     max(0, (ps["shots_on"] or 0) - goals),
                "fouls_drawn":  ps["fouls_drawn"] or 0,
                "clearances":   ps["clearances"] or 0,
            }

            # STATS use only M1 (rival quality), not M2 (stage importance).
            # Stage factor rewards decisive actions (goals, assists), not background stats.
            c = clamped(m1, 1.0, 1.0, 1.0, 1.0)
            base_total = sum(
                sb.get(k, 0) * v for k, v in stat_counts.items() if v > 0
            )
            new_pts = round(base_total * c, 2)
            new_m2 = 1.0  # store 1.0 in m2 column for STATS events
        else:
            skipped += 1
            continue

        cur.execute(
            "UPDATE player_events SET m2 = %s, pts = %s WHERE id = %s",
            (new_m2, new_pts, ev["id"]),
        )
        updated += 1

        if updated % 2000 == 0:
            conn.commit()
            print(f"  {updated} events updated...")

    conn.commit()
    print(f"Events updated: {updated}, skipped: {skipped}\n")

    # ── 3. Rebuild sfa_season_scores for every player × competition ──────────
    print("Rebuilding season scores...")

    cur.execute("""
        SELECT pe.player_id, f.competition_id, f.season,
               SUM(pe.pts) as total_pts,
               COUNT(DISTINCT pe.fixture_id) as matches,
               pe.event_type,
               SUM(pe.pts) as evt_pts,
               COUNT(*) as evt_count
        FROM player_events pe
        JOIN fixtures f ON f.id = pe.fixture_id
        GROUP BY pe.player_id, f.competition_id, f.season, pe.event_type
    """)
    rows = cur.fetchall()

    # Aggregate into (player, comp, season) buckets
    score_map: dict[tuple, dict] = defaultdict(lambda: {"total": 0.0, "breakdown": {}})
    for r in rows:
        key = (r["player_id"], r["competition_id"], r["season"])
        score_map[key]["total"] += float(r["evt_pts"])
        etype = r["event_type"].lower()
        if etype not in score_map[key]["breakdown"]:
            score_map[key]["breakdown"][etype] = {"count": 0, "pts": 0.0}
        score_map[key]["breakdown"][etype]["count"] += r["evt_count"]
        score_map[key]["breakdown"][etype]["pts"]   = round(
            score_map[key]["breakdown"][etype]["pts"] + float(r["evt_pts"]), 2
        )

    # Matches played (fixtures with ≥1 event)
    cur.execute("""
        SELECT pe.player_id, f.competition_id, f.season, COUNT(DISTINCT pe.fixture_id) as m
        FROM player_events pe JOIN fixtures f ON f.id = pe.fixture_id
        GROUP BY pe.player_id, f.competition_id, f.season
    """)
    matches_map: dict[tuple, int] = {
        (r["player_id"], r["competition_id"], r["season"]): r["m"]
        for r in cur.fetchall()
    }

    scores_done = 0
    for (player_id, comp_id, season), data in score_map.items():
        total = round(data["total"], 2)
        bd    = data["breakdown"]
        mp    = matches_map.get((player_id, comp_id, season), 0)

        for key in bd:
            bd[key]["pct"] = (
                round(bd[key]["pts"] / total * 100, 1) if total > 0 else 0.0
            )

        cur.execute("""
            INSERT INTO sfa_season_scores
                (player_id, competition_id, season, total_pts, matches_played, breakdown, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT ON CONSTRAINT uq_sfa_season_score
            DO UPDATE SET
                total_pts     = EXCLUDED.total_pts,
                matches_played= EXCLUDED.matches_played,
                breakdown     = EXCLUDED.breakdown,
                last_updated  = NOW()
        """, (player_id, comp_id, season, total, mp, json.dumps(bd)))

        scores_done += 1
        if scores_done % 500 == 0:
            conn.commit()
            print(f"  {scores_done} scores updated...")

    conn.commit()
    print(f"Season scores updated: {scores_done}\n")
    print("Done.")


if __name__ == "__main__":
    main()
