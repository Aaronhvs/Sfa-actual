# Decisions: Tournament knockout bracket

## Context

Tournament detail currently renders knockout fixtures as independent stage columns. That
representation loses bracket branches, two-leg aggregate scores and the authoritative champion.

## Decisions

- Extend the existing tournament detail read model instead of adding a second endpoint.
- Resolve `champion` from `competition_achievements.phase = winner` joined to `teams`.
- Keep fixtures as the source for bracket rounds and aggregate two legs in the frontend by stage
  and unordered team pair.
- Reconstruct later-round ordering by matching each next-round participant with the winner of a
  previous tie. Chronological order is only a fallback for incomplete future rounds.
- Render a dedicated tournament bracket component. Do not couple club fixtures to World Cup routes
  or World Cup-specific seeding rules.
- Keep the full bracket horizontally scrollable on narrow screens so node and connector geometry
  remains stable.

## Boundaries

- No migration is required.
- No external API request is added to page load.
- Scoring and achievement inference are unchanged.
- The existing World Cup bracket remains untouched.

## Agent routing

DDD Designer needed: no. This extends an existing read model and presentation component without
introducing a new domain lifecycle.
