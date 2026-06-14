# 0030 - World Cup Match Detail Implementation Plan

## Checklist

- [x] 1. Record baseline backend test status before adding tests. (`python -m pytest` unavailable in the Windows host environment: pytest is not installed.)
- [x] 2. Add match-detail DTOs to `domain/world_cup_ports.py`.
- [x] 3. Extend `WorldCupRepositoryProtocol` with `get_fixture_detail`.
- [x] 4. Add `fetch_world_cup_fixture_detail` parsing to `APIFootballProvider`.
- [x] 5. Add Redis caching and serialization for fixture detail in `WorldCupRepository`.
- [x] 6. Add `GetWorldCupFixtureDetailUseCase` with not-found behavior.
- [x] 7. Wire the use case exclusively in `core/dependencies.py`.
- [x] 8. Add fixture-detail Pydantic schemas to `api/v1/schemas/wc_schemas.py`.
- [x] 9. Add `GET /wc/fixtures/{fixture_id}` to `wc_router.py`.
- [x] 10. Add happy-path and not-found requests to `http/world_cup.http`.
- [x] 11. Add provider parsing tests for complete and partial payloads.
- [x] 12. Add use-case tests with a concrete protocol fake.
- [x] 13. Add frontend match-detail types and API client function.
- [x] 14. Make World Cup fixture cards keyboard-accessible links.
- [x] 15. Add `/mundial/partido/:fixtureId` route and `MundialMatchPage`.
- [x] 16. Implement summary, lineups and statistics tabs with empty states.
- [x] 17. Add tournament-token CSS for desktop, tablet, mobile and reduced motion.
- [x] 18. Run focused backend tests and static checks.
- [x] 19. Run `npm run build`.
- [x] 20. Verify the live endpoint with a known World Cup fixture.
- [x] 21. Extend lineup player DTO/schema with nullable SFA identity and points.
- [x] 22. Enrich cached provider lineups from active fixture scores in PostgreSQL.
- [x] 23. Add repository tests for scored and unprocessed lineup players.
- [x] 24. Replace redundant summary information with tactical pitches.
- [x] 25. Display written lineups below the pitches and SFA points after processing.
- [x] 26. Re-run backend checks, frontend build and live fixture verification.

## Agent Routing Brief

No `[DDD]` items are required. This is a read-only extension using existing World Cup
DTO and repository patterns. Implementation remains Router -> Use Case -> Repository
-> Provider, with Redis as repository-level cache.
