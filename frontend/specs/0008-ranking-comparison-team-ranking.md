# Ranking loading, comparison workbench and team ranking

Status: implemented; browser verification completed locally with public player
data and a read-only response captured from the staged team API against the VPS.
User approved these three changes; scoring proposals remain deferred.

## Scope

- Local spinner for the ten-player list. The podium is not remounted on pagination.
- Compact comparison views with contextual SFA metrics first and match evidence.
- Public descriptive team ranking UI backed by backend spec 0063.
- No new M1/M3, qualifying-goal or efficiency scoring rules.

## Design Decisions

- Preserve existing SFA typography, dark tokens, subdued club colors and white values.
- One comparison panel at a time; keyboard-accessible tabs rather than all groups
  stacked. Monthly evolution remains available as its own view.
- Clearly name existing M1/M3 proxies; do not claim absolute rival quality or
  final-result decisiveness before the deferred context models exist.
- Real player photos and match club crests; highlighted matches link to detail.
- Team score is an experimental descriptive index, not a calibrated prediction.
- Show ELO, normalized observed individual SFA, sample coverage, fallback seasons,
  single-component scores and scored-data cutoff; expand methodology on demand.

## Completed Checklist

- [x] Read product/brand context and design references.
- [x] Preserve committed list and dimensions during loading; animate new results only.
- [x] Handle local retry and restore the committed page indicator on failure.
- [x] Preserve ranking deep links instead of resetting them on initial search debounce.
- [x] Replace comparison scroll stack with tabs, impact summary and match evidence.
- [x] Keep all statistical views and chart accessible; support arrow/Home/End keys.
- [x] Neutralize bars when data cannot be compared; keep missing values distinct.
- [x] Connect typed team API, season selector, league filter, search and pagination.
- [x] Expose model limitations and observed-data cutoff without implying live freshness.
- [x] Production TypeScript/Vite build passes.
- [x] Review screenshots at 1440px desktop and 390px mobile.

## Browser Verification

Playwright CLI, local preview at port 5174; no added frontend test dependency.

- Delayed player page response: spinner visible, old cards hidden, same podium DOM
  element, unchanged list height, ten cards after success.
- HTTP 503 then retry: prior card DOM preserved, committed page retained and real
  retry button clickable; spinner removed after successful response.
- Direct page=2 remains page=2 after the initial debounce interval.
- Rapid search, empty result and clear: page container preserved and podium returns.
- Mobile player pagination: ten results and no document horizontal overflow.
- Comparison: exactly one metric section per active view, impact default, keyboard
  switching works, desktop/mobile screenshots and no document overflow.
- Team UI: twenty real response rows, season metadata, visible scoring cutoff,
  methodology disclosure and containment of the mobile table's horizontal scroll.
- API numerical/attribution tests and real read-only SQL integration are documented
  in backend/specs/feature/0063-public-team-ranking/decisions.md.

Artifacts under output/playwright are local review evidence, not production data.
