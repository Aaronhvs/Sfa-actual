"""
Seed competition_stages for all competitions.

Run AFTER ingesting competitions so their IDs exist in the DB:
    python scripts/seed_competition_stages.py

Stage names match ROUND_TO_STAGE in api_football.py:
  "group", "round_of_16", "quarter", "semi", "final", "regular"

Stage factors rationale:
  - CL: highest stakes globally (1.5 group → 2.8 final)
  - Domestic leagues: neutral 1.0 (no stage concept for regular season)
  - Copa del Rey / Supercopa: moderate (0.9 regular → 1.4 final)
  - Other national cups (FA Cup, Coupe de France, DFB-Pokal, Coppa Italia):
    same scale as Copa del Rey
"""
from __future__ import annotations

import psycopg2
import psycopg2.extras

DB = dict(host="localhost", port=5432, user="sfa", password="sfa", dbname="sfa")

# Map (competition_name, stage) → stage_factor
STAGE_SEEDS: list[tuple[str, str, float]] = [
    # Champions League
    ("Champions League", "group",       1.5),
    ("Champions League", "round_of_16", 1.8),
    ("Champions League", "quarter",     2.0),
    ("Champions League", "semi",        2.3),
    ("Champions League", "final",       2.8),

    # Domestic leagues — one "regular" stage covers all matchdays
    ("La Liga",       "regular", 1.0),
    ("Premier League","regular", 1.0),
    ("Bundesliga",    "regular", 1.0),
    ("Serie A",       "regular", 1.0),
    ("Ligue 1",       "regular", 1.0),

    # Copa del Rey
    ("Copa del Rey", "regular",     0.9),
    ("Copa del Rey", "round_of_16", 1.1),
    ("Copa del Rey", "quarter",     1.3),
    ("Copa del Rey", "semi",        1.6),
    ("Copa del Rey", "final",       2.0),

    # Supercopa de España
    ("Supercopa de España", "semi",  1.7),
    ("Supercopa de España", "final", 2.1),

    # FA Cup
    ("FA Cup", "regular",     0.9),
    ("FA Cup", "round_of_16", 1.1),
    ("FA Cup", "quarter",     1.3),
    ("FA Cup", "semi",        1.6),
    ("FA Cup", "final",       2.0),

    # Coupe de France
    ("Coupe de France", "regular",     0.9),
    ("Coupe de France", "round_of_16", 1.1),
    ("Coupe de France", "quarter",     1.3),
    ("Coupe de France", "semi",        1.6),
    ("Coupe de France", "final",       2.0),

    # DFB-Pokal
    ("DFB-Pokal", "regular",     0.9),
    ("DFB-Pokal", "round_of_16", 1.1),
    ("DFB-Pokal", "quarter",     1.3),
    ("DFB-Pokal", "semi",        1.6),
    ("DFB-Pokal", "final",       2.0),

    # Coppa Italia
    ("Coppa Italia", "regular",     0.9),
    ("Coppa Italia", "round_of_16", 1.1),
    ("Coppa Italia", "quarter",     1.3),
    ("Coppa Italia", "semi",        1.6),
    ("Coppa Italia", "final",       2.0),
]


def main() -> None:
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT id, name FROM competitions")
    comp_id_map: dict[str, int] = {r["name"]: r["id"] for r in cur.fetchall()}
    print(f"Found {len(comp_id_map)} competitions: {list(comp_id_map.keys())}")

    inserted = skipped = missing = 0
    for comp_name, stage, factor in STAGE_SEEDS:
        comp_id = comp_id_map.get(comp_name)
        if comp_id is None:
            print(f"  MISSING competition: {comp_name!r} — ingest it first")
            missing += 1
            continue

        cur.execute(
            """
            INSERT INTO competition_stages (competition_id, stage, stage_factor)
            VALUES (%s, %s, %s)
            ON CONFLICT (competition_id, stage) DO UPDATE
                SET stage_factor = EXCLUDED.stage_factor
            """,
            (comp_id, stage, factor),
        )
        inserted += 1

    conn.commit()
    print(f"\nDone. Upserted: {inserted}, missing competitions: {missing}")
    conn.close()


if __name__ == "__main__":
    main()
