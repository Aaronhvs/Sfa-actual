# Plan: canonical fixture sides and UEFA Super Cup M2

- [x] Update `IngestionRepository.upsert_fixture` conflict values with all canonical fixture
  identity and schedule fields.
- [x] Add repository coverage proving the conflict statement updates both teams, competition,
  season and kickoff as well as status and score.
- [x] Select `PlayerEvent.team_id` in scoring context and resolve home/away snapshots from that
  canonical relation.
- [x] Add a legacy fallback for null event team and closed validation for contradictory sides.
- [x] Add unit tests for home, away, legacy and invalid side resolution.
- [x] Add migration `0050_normalize_uefa_super_cup_stage_factor.sql` with an idempotent upsert to
  `1.30`.
- [x] Bootstrap late club entrants from prior-season ELO or the approved 1000 default.
- [x] Keep strict seed coverage validation after the late-entry bootstrap.
- [x] Run baseline and post-change pytest suites, changed-file flake8/isort and diff checks.
- [ ] Commit and deploy API/worker with Beat paused.
- [ ] Apply migration 0050 and verify the single UEFA Super Cup final row is `1.30`.
- [ ] Reingest fixture external id `1552735` with forced detail refresh.
- [ ] Replay season-2026 club ELO and scoring once.
- [ ] Verify zero event-side inconsistencies and audit PSG/Rennes calculation details.
- [ ] Restart Beat and confirm worker health.

## Agent Routing Brief

No DDD task is required. Implementation stays in the existing ingestion and scoring adapters.
