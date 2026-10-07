# Plan: Team ranking football enrichment

## Files

- Domain: `src/sfa/domain/team_ranking_ports.py` (DTO defaults and batch read port).
- Repository: `src/sfa/infrastructure/repositories/team_ranking_repository.py` (player metadata and page form query).
- Use case: `src/sfa/application/use_cases/get_team_ranking.py` (featured selection and post-pagination enrichment).
- Schema: `src/sfa/api/v1/schemas/team_ranking.py` (nested response fields).
- Existing ranking repository/use-case/HTTP tests and `scripts/verify_team_ranking_readonly.py`.

## Implementation checklist

- [x] Record pre-change test baseline before adding tests.
- [x] Add frozen match/featured DTOs, trailing player defaults and explicit batch repository method.
- [x] Extend current player query with name/photo, preserving all aggregation/scoring semantics.
- [x] Implement one bounded form read for page team IDs, requested season/kind, FT/AET/PEN and as_of.
- [x] Select current-season highest total player, deterministic ties; enrich form only after pagination.
- [x] Extend existing HTTP response schemas without changing route or DI.
- [x] Update complete protocol Fakes; test transfers, current/prior, totals/ties, negative/zero, empty pages.
- [x] Test executed result SQL for last-five ordering, missing scores, penalties, future/live and season exclusions.
- [x] Verify nested HTTP serialization and default backward-compatible fields.
- [x] Update read-only script for five explicit-season nonempty-page queries and enrichment checks; do not run it.
- [x] Run full focused tests and scoped flake8/isort; record broader baseline limitations.

## Agent Routing Brief

**DDD Designer needed:** no. Read-side DTO enrichment only, no entities or scoring invariants.
Architecture/spec phase is followed by the user-authorized implementation phase in this session.

## Verification

Local tests use Fakes and disposable in-memory SQLite only, never configured DB connections.
Integration strategy: existing ASGI script with lifespan disabled, enforced PostgreSQL
READ ONLY transaction, statement timeout and generic plans; compare stable normalization across
filters/pages, bounded chronological form and current-season featured evidence.
The frontend owner completed this read-only integration and reported success (see below).

Baseline: default shell `DEBUG=release` prevented collection (invalid boolean). With a process-only
`DEBUG=false` override, `python -m pytest tests/ -q --disable-warnings --maxfail=3` passed: 639 tests.
No application config or environment files changed.

Final local verification:
- Full suite: 661 passed.
- Focused ranking suite: 68 passed; 100% line coverage for all four modified runtime modules.
- Scoped flake8, isort --check-only and git diff --check passed.
- Read-only verifier extended with `--fixture-json`, five nonempty-page reads / four empty-page reads,
  actual fixture evidence and max current-season individual total assertions, and first/second-page
  response/form-query latency checks (30s/5s defaults, configurable).
- No fixed scored-data date expectations. Fixture dates compare only to actual source rows and request as_of.
- VPS capture was not executed by this session. The frontend owner completed the isolated
  --rm --no-deps temporary-mount verification and reported all enrichment checks passing;
  source mounts are read-only and output JSON uses a separate writable capture mount.
- After the user's initial capture request, SSH only listed running container names; an inspect
  command failed during template parsing. No remote source, service or DB changes were performed.
  The user subsequently took ownership of remote transfer/execution; no further SSH was attempted.

Capture CLI (inside the user's isolated verifier container, not a deployment):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src DEBUG=false python /capture-src/verify_team_ranking_readonly.py \
  --fixture-json /capture/team-ranking-football.json \
  --max-response-seconds 30 --max-enrichment-seconds 5
```

Use the container's actual source path for PYTHONPATH. Source mounts must be read-only;
only `/capture` is writable. Do not execute the app entrypoint or ASGI lifespan. The script
sets READ ONLY before any API reads, with a 30s statement timeout and forced generic plans.

## Reported read-only integration

- [x] Record frontend owner's successful isolated VPS verification; no independent remote re-run.
- Five queries on the first page; total 2.724s, form query 0.018s.
- Second-page total 2.520s, form query 0.011s.
- All enrichment checks passed; population 751 clubs / 48 national teams.
- Reported source scored-data cutoff: September 20. No exact timestamp or fixed freshness asserted.
- First/second-page latency checks pass the default 30s total / 5s form budgets.
- Local design preview only. No deployment, migrations, scoring changes or commit.
