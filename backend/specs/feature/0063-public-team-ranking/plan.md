# Plan: Public Team Ranking

## Files To Create

- [x] `src/sfa/domain/team_ranking_ports.py`: frozen input/output DTOs and read port.
- [x] `src/sfa/application/use_cases/get_team_ranking.py`: protocol, result and descriptive calculation.
- [x] `src/sfa/infrastructure/repositories/team_ranking_repository.py`: bounded aggregate read model.
- [x] `src/sfa/api/v1/schemas/team_ranking.py`: typed response contract.
- [x] `src/sfa/api/v1/teams.py`: public GET input adapter.
- [x] `http/teams.http`: happy path, filters, fallback and validation examples.
- [x] `tests/use_cases/test_get_team_ranking.py`: complete Fake, risk-focused math/behavior tests.
- [x] `tests/repositories/test_team_ranking_repository.py`: query shape, attribution and adapter tests.
- [x] `tests/test_team_ranking.py`: response serialization and HTTP validation.
- [x] `scripts/verify_team_ranking_readonly.py`: real PostgreSQL verification, isolated staged code, no writes.

## Files To Modify

- [x] `src/sfa/core/dependencies.py`: repository and use-case factories only.
- [x] `src/sfa/infrastructure/repositories/__init__.py`: export repository.
- [x] `src/sfa/main.py`: import/register teams router and tag.

## Implementation Checklist

- [x] Inspect architecture, local skills, models and baseline tests; record limitations.
- [x] Define immutable domain contract, including source seasons and unknown availability.
- [x] Implement season parsing, percentiles, shrinkage, fallback, filters and deterministic pagination.
- [x] Implement constant-count aggregate reads with verified historical attribution and coherent version selection.
- [x] Add DI factories and repository export.
- [x] Add typed router/schemas, main registration and HTTP examples.
- [x] Write Fake-based use-case tests: empty, invalid, fallback, ties, cohort stability, coverage and weights.
- [x] Test SQL and adapter: no bonus table, aggregate-before-minutes, coherent version and bounded window.
- [x] Test HTTP: exclusivity, scope validation, pagination and nullable serialization.
- [x] Run targeted tests and complete pytest suite; record pre-existing/environment failures.
- [x] Run scoped flake8 and isort checks; new-module line coverage 100%.
- [x] Review diff, document local DB limitation and successful VPS read-only integration, preserve unrelated changes.
- [x] Export public live response fixture at frontend owner's explicit request; no frontend source changes.
- [x] Correct domestic league display from verified current-season fixture participation and add regressions.
- [x] Normalize national/national_team alias to stored participant kind and test HTTP/repository behavior.
- [x] Repeat full/targeted/style checks and VPS read-only verification; refresh public response fixture.

## Verification

1. Process-only `DEBUG=false`; run pytest for new modules then `pytest tests/`.
2. Run flake8/isort on changed Python files, without unrelated formatting churn.
3. Verify repository aggregates a realistic synthetic dataset and exposes fallback seasons.
4. Live database read only if accessible; never deploy or commit.

## Agent Routing Brief

**DDD Designer needed:** no

This is a read-side projection of existing teams, fixtures, ELO and individual
scores. DTOs and transparent descriptive statistics only; no entities, scoring
value objects, aggregates or scoring rules are introduced. User explicitly
authorized implementation after this architecture/spec phase in the same turn.
