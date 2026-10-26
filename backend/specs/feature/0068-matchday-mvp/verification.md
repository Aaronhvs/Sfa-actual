# 0068 — Production verification

Verified on 2026-10-26, America/Santiago.

## Release

- Main implementation commit: `ebb1a1191a24bab5c9de6a5207f949df72c8767f`.
- Production source commit: `e60a2ac94a9a8fcd8841640d7c22a66b38c76e8d`.
- Image: `sfa-matchday-mvp:20261026-ebb1a11`, shared by API, worker and beat.
- Source: `/home/ubuntu/sfa-releases/matchday-mvp-ebb1a11`.
- Compose: the release's `backend/docker-compose-prod.yml` plus
  `/home/ubuntu/sfa-change-backups/matchday-mvp-20261026/compose.matchday-mvp.yml`.
- The implementation commit was applied to the previously running source `c8e4ca0`.
  Only its 18 backend files changed. Existing published position/ranking fixes were preserved.
  The dirty primary workspace and the old VPS checkout were not deployed.
- No schema migration, provider ingestion or points recalculation was performed for this feature.
  Existing worker tasks finished before API/worker/beat were switched; normal scheduling resumed.
  Rollback configuration is saved in the same audit directory as `rollback.json`.

## Tests

| Source | Passed | Skipped | Failed |
| --- | ---: | ---: | ---: |
| Clean main baseline, PostgreSQL tests disabled | 760 | 20 | 0 |
| Running-image baseline, isolated leads database | 1188 | 28 | 0 |
| Clean candidate, isolated leads/MVP databases | 800 | 10 | 0 |
| Final release, isolated leads/MVP databases | 1218 | 28 | 0 |

The 30 new tests cover round completion, deterministic ties, single-match scoring including
STATS, final statuses, knockout legs, missing/contradictory appearance evidence, published
positions, each reason, exact HTTP schemas, empty data, unknown competitions and cache failures.
PostgreSQL writes were restricted to dedicated `leads_test` and `mvps_test`; each test rolls back.
No historical health-test fixture errors were reproduced.

New-module statement coverage: domain 98.68%, tournament use case 96.49%, latest use case 100%,
repository 100%, cache 97.56%, schemas 100%. Changed Python modules pass flake8/isort.

## Public and browser checks

- `/api/v1/tournaments/mvps/latest?season=2026`: HTTP 200, eight entries in the exact requested order:
  Champions, La Liga, Premier, Serie A, Bundesliga, Ligue 1, Europa, Conference.
- Competition objects match `/api/v1/tournaments?season=2026`, including fixture counters.
- `/api/v1/tournaments/1/mvps?season=2026`: ten entries, `matchday-1` through `matchday-10`, in order.
- Independent read-only SQL matched all ten La Liga winners and exact points.
- The 17 distinct player/competition contexts across those rounds and the latest rail were checked
  against the public ranking with the same scope/competition: zero position discrepancies.
- La Liga round 10: Kylian Mbappé, player 888, fixture 1570426, **3317.99** points.
  The public match-detail response and its lineup show the identical value (UI rounds to 3318).
- Existing C. Cásseres profile remains MC; leads has no DC group. Raphinha still displays correctly.
- Existing competitions and season 1900 return 200 with empty items; unknown competition returns 404.
- Desktop 1440px: `/torneos` displays eight MVPs below competitions.
- Mobile 390px: the Jornada tab displays eight MVPs without horizontal page overflow.
- `/torneos/1?season=2026`: MVP card and ten history buttons work on desktop/mobile;
  keyboard selection of round 9 changes the card, and round 10 links to the correct match.

Read-only benchmark over current data: latest cold 3.42s / warm 0.81s, 52 / 9 queries,
bounded per competition rather than per player/fixture. Representative EXPLAIN execution:
fingerprint 104.85ms, performance aggregation 81.68ms. No additional index was needed.

## Data limitations

`complete` describes all known fixtures in a supported round, not guaranteed provider inventory
or score-ingestion coverage. Unscored rounds do not receive an invented winner.
Continental qualifying games without round metadata and malformed historical cup stages are
excluded rather than labeled as league matchdays or many separate finals. Two-leg inference
requires two coherent reverse-home fixtures; an ambiguous tie remains unsupported until its
calendar evidence is available. These exclusions do not affect the eight current featured rounds.

Detailed logs, SQL audit, coverage, deployment state and public JSON are under
`output/matchday-mvp-20261026/` locally and
`/home/ubuntu/sfa-change-backups/matchday-mvp-20261026/` on the VPS. Browser captures are under
`output/playwright/mvp-*.png`.
