# Plan: Tournament knockout bracket

- [x] Add optional champion team to tournament DTO and API schema.
- [x] Query the authoritative winner achievement in `TournamentRepository`.
- [x] Cover champion serialization through the tournament use case.
- [x] Build two-leg aggregate ties for round of 16, quarters, semis and final.
- [x] Order branches by tracing winners into the following round.
- [x] Render connected desktop bracket with champion at the center.
- [x] Preserve stable geometry and horizontal access on mobile.
- [x] Run backend tests (`547 passed`) and frontend production build.
- [x] Verify formatting and responsive presentation with Playwright.
