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

## Publication completed

- Main source commit: `cefb4d9`; production source with preserved runtime extras:
  `9b2d230d428fa94957b7291baefbce0755d14e3c`.
- Active API, worker and beat image: `sfa-psg-titles:20261028-9b2d230`.
- Complete runtime suite: **1282 passed, 48 skipped**, new-code coverage **92.77%**.
  Final provider regression module after its last refinement: **3 passed**.
  Clean-main local suite: **863 passed, 32 skipped**. Lint/import checks passed.
- PostgreSQL clone verified exact repeat, bonus-only rebuild, strict-CAS revert,
  stale-cut rejection, publication lock contention, preserved IDs and full closure.
- Fresh live backup: `production-before-publication.dump` (174779238 bytes).
- Committed journal: `psg-titles-2025-e1c679e2c2b8466491cc4e1f9112e390`.
- Before fingerprint: `ee28c27309a386c99d415bd522303977b1bf52954a612eea580ec8dee2ce73e1`.
- After fingerprint: `52e6ceebe6e2a6c19d2359e7a6a092aa890f53e103f753049a07512639fd7d41`.
- Guard checks compare count and two independently seeded, typed PostgreSQL record
  checksums, then SHA-256 the cut. Target rows are captured in full. This avoids
  repeatedly serializing/sorting every large score-details JSON for dependency CAS.
- Public player/achievement endpoints return HTTP200. Dembélé now has all five PSG
  winning titles; his total changes from **60464.88 to 70731.30**: Ligue1 +7776.42,
  UEFA Super Cup +945, Intercontinental +1545. Champions/Trophée bonuses unchanged.
- All unchanged-table/dependency guards passed: event scores/raw events, positions,
  strengths/ELO and rule configuration; the season-2026 top50 also matched exactly.
- Health: database/Redis connected. MVP endpoint still returns eight featured
  competitions. Worker/beat resumed; two season-2025 cache entries invalidated.

Intercontinental participation/raw stats and the title bonus are published. Its
individual performances remain unevaluated until legitimate scoring context is
available; no synthetic player events, M1, performance rank or scored match was added.
