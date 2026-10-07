# Football-First Team Ranking

User approved real recent results and featured player as the primary team view.

## Scope

- Preserve the experimental ranking formula and all existing filters.
- Primary view: club crest/name, last five results, highest individual SFA contributor,
  relative team score out of 100. No invented trend labels or win probabilities.
- Current-season completed fixtures only for form; oldest to newest. The interface
  neutralizes all penalty-game outcomes because shootout winner evidence is
  unavailable; backend tied penalty games already return unknown outcome.
- Featured player uses total individual SFA in the existing ten-match window,
  verified appearance-team attribution, current season only, not historical fallback.
- Row expansion reveals actual fixtures, ELO, individual normalized performance,
  sample coverage and source seasons. Methodology remains available.
- Mobile rows become stacked summaries, without a horizontally scrolled table.
- Existing SFA direction and approved composition: no additional raster mock needed.

## Verification

- [x] TypeScript and production build.
- [x] Backend enrichment tests and bounded query validation: 661 tests; enforced
  read-only ASGI integration against the VPS, five reads, 2.724 seconds total,
  0.018 seconds for page form. Existing scores unchanged.
- [x] Desktop/mobile screenshots with captured real read-only data.
- [x] Search, filter, pagination, disclosure, fixture/player links and missing data.
  UI pagination/filter checks use a controlled subset of the captured response;
  real endpoint pagination/filter invariants are covered by read-only integration.
- [x] No document horizontal overflow at 320, 390, 768, 1024 and 1440 pixels;
  tablet form/featured column bounds do not overlap.
- [x] Controlled edge-case UI checks: all PEN outcomes neutral, null featured
  player shows missing-data state, YYYY-YY source season displays correctly.

Local review: http://127.0.0.1:5175/teams. Review-only server under output/playwright
serves the captured first twenty teams for season-2026; other APIs use the public
API. No fixture data or mock middleware is shipped in production code. No deploy
or commit performed for this design iteration.

## Post-Publication Coverage Audit

The Barcelona 120/129 counter counted nine goalkeeper appearances as missing
scores, although current scoring explicitly has no GK position group. Read-only
production audit of the current season's last-ten-match team windows confirmed
16,213 outfield appearances with stats scores and zero missing, plus 611 goalkeeper
appearances intentionally without SFA scores. No recalculation or fabricated zero
scores needed. Remove the coverage counter and its partial-data UI heuristic;
retain the raw API audit fields. Name the individual component as outfield-player
performance and disclose the keeper limitation in methodology. Formula unchanged.
