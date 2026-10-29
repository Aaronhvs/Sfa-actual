# 0070 — PSG 2025/2026

## Verified source cut

Seven sequential API-Football GETs archived under
`/home/ubuntu/sfa-change-backups/psg-trophy-repair-20261028/`, with response headers,
timestamps and SHA-256 request journal. No provider call is made by prepare/apply.

- Ligue 1: 306 regular fixtures, final table of 18 teams, PSG first. Missing fixture
  1388000 is an administrative AWD, not a played match; Nantes and Toulouse have
  33 appearances in the provider's table. Import its metadata only. Do not invent
  player events, stats or played minutes.
- UEFA Super Cup 1377400: 2–2, PSG wins the separate shootout 4–3. Source elapsed
  120 is not proof of extra time and is not used to create events or minutes.
- FIFA Intercontinental Cup 1491683: 1–1, PSG wins the separate shootout 2–1.
  Both squads' real participation totals 1320 player-minutes per side and starters
  have 120 minutes. Its title-only participation denominator is 120, not 90.
  Archive and retain the actual supplied player stats as raw facts; no PES,
  pre-match strengths, scored appearances or performance ranks are fabricated.

The isolated production clone has 30 pre-existing orphan achievement bonuses in
season 2026. Its dump restores with one FK validation failure. Recreate that FK
as NOT VALID **in the clone only**, so subsequent writes are still checked. Do not
delete those records or relax production constraints as part of this repair.

## Procedure

1. Reserve migration 0058 against production's actual schema (0055–0057 belong to
   runtime extras). Apply the additive columns in the clone before its tests.
2. Run `scripts/correct_psg_titles.py --directory /evidence` in the isolated clone.
   Default is rollback. `--commit` commits; `--production` is additionally required
   against a database whose name does not end in `_test`.
3. The CLI prepares a frozen source/snapshot cut, takes the try-only position
   publication advisory lock, writes and fsyncs an intent journal, then enables
   the existing publication GUC only for the transaction's bounded writes. It
   disables that GUC before reading and validating the actual result.
4. Validate all affected players, CA/PAB/SSS closure, retained existing CA IDs,
   bonus-only SSS rows, repeat execution and strict-CAS revert. Rebuild of an
   unscored title-only competition must retain its bonus and zero scored matches.
5. Layer source onto the active tested image/source release, preserving position,
   scoring, search and 0069 runtime extras. Do not upgrade dependencies.
6. Before live apply, save a fresh backup, stop beat, drain active worker tasks,
   stop the worker, take a new dry-run cut, then commit only if its fingerprint is
   unchanged. Import metadata, infer only the three target competitions, refresh
   bonuses through the existing UC and refresh season-2025 individual honors.
7. Invalidate caches for the corrected period, activate the compatible release,
   verify player/ranking/title APIs and resume worker/beat. Verify season-2026 and
   national World Cup scores, positions, ELO and global v4 config stayed intact.

## Recovery

`--revert <committed-journal-key> --commit --production` restores the exact before
rows and IDs only while the whole affected cut and dependencies still match the
recorded after fingerprint. Newer activity causes rejection. Never disable a
trigger or discard intervening activity. The before image and database dump are
retained independently.

## Tests

Local baseline before new tests: **830 passed, 30 skipped**. Tests against a clone
require `TITLE_TEST_DATABASE_URL` ending in `/sfa_psg_titles_2025_test` and
`TITLE_TEST_EVIDENCE_DIR`; they always roll back. Do not point those variables at
production. Final validation and live results are recorded alongside the source
evidence and deployment manifest.
