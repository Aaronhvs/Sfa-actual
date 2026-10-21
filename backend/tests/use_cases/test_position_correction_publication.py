from __future__ import annotations

import json
from dataclasses import asdict, replace

import pytest

from sfa.application.use_cases.publish_position_correction import (
    PublishPositionCorrectionUseCase,
    RevertPositionCorrectionUseCase,
)
from sfa.application.use_cases.simulate_position_correction import SimulatePositionCorrectionUseCase
from sfa.domain.player_positions.ports import PositionCorrectionRepository
from sfa.domain.player_positions.publication import (
    PositionCorrectionCapture,
    PositionCorrectionRequest,
    PositionPublicationResult,
    canonical,
)
from sfa.domain.scoring.event_engine import EventScoringEngine
from sfa.domain.scoring.services import SFAScoringService
from sfa.domain.scoring.value_objects import ScoringConfig
from tests.use_cases.test_calculate_scores_for_rules_version import (
    FakePlayerEventScoreRepository,
    FakeScoringRulesVersionRepository,
    _make_goal_event,
    _make_rules_version,
    _make_stats_event,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeCorrectionRepository:
    def __init__(self, capture):
        self.capture_result = capture
        self.result = None
        self.applied = []
        self.reverted = []

    async def capture(self, request, rules_version_id):
        return self.capture_result

    async def published(self, batch_id):
        return self.result

    async def apply(self, plan):
        self.applied.append(plan)
        self.result = PositionPublicationResult(plan.batch_id, "published", 2, 1)
        return self.result

    async def revert(self, batch_id, actor):
        self.reverted.append((batch_id, actor))
        return PositionPublicationResult(batch_id, "reverted", 2, 1)


def context():
    request = PositionCorrectionRequest(10, 989, 5, 501, "2024", "DEL", (100,),
                                        "2026-10-19T12:00:00+00:00", "user:confirmed-role", "Curated role", "reviewer")
    version = _make_rules_version(config=ScoringConfig.default_v2())
    original = [_make_goal_event(), replace(_make_stats_event(), player_id=10, fixture_id=100),
                replace(_make_goal_event(event_id=3, fixture_id=101), player_position="EXT")]
    scorer = EventScoringEngine()
    rows = []
    for event in original:
        score = asdict(scorer._score_event(event, SFAScoringService(version.config), version.id))
        score.update(id=event.event_id, created_at="2026-01-01T00:00:00+00:00")
        rows.append(score)
    rollup = {"id": 21, "competition_id": 1, "total_pts": sum(r["final_points"] for r in rows),
              "achievement_bonus_pts": 720, "matches_played": 2}
    capture = PositionCorrectionCapture(canonical({"rank_dependent_achievements": [], "sentinel": "input"}),
                                         canonical(rows), canonical([rollup]), "engine-v1")
    repo = FakeCorrectionRepository(capture)
    events = FakePlayerEventScoreRepository([replace(e, player_position="EXT") for e in original])
    rules = FakeScoringRulesVersionRepository(version)
    return request, repo, events, rules, SimulatePositionCorrectionUseCase(repo, events, rules)


@pytest.mark.anyio
async def test_simulation_preserves_scored_baseline_and_excludes_unapproved_fixture_without_writes():
    request, repo, events, _, simulation = context()
    assert isinstance(repo, PositionCorrectionRepository)
    result = await simulation.execute(request, 1)
    changes = json.loads(result.event_changes_json)
    assert {c["before"]["event_id"] for c in changes} == {1, 2}
    assert {c["before"]["position"] for c in changes} == {"MC"}
    assert {c["after"]["position"] for c in changes} == {"DEL"}
    rollup = json.loads(result.rollup_changes_json)[0]
    assert rollup["after"]["achievement_bonus_pts"] == 720
    assert rollup["after"]["matches_played"] == 2
    assert json.loads(result.report_json)["baseline_events_verified"] == 3
    assert events.upserted == events.bulk_rebuild_calls == repo.applied == []
    assert (await simulation.execute(request, 1)).manifest_hash == result.manifest_hash


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["missing_version", "inactive", "missing_event", "baseline", "rollup",
                                      "missing_rollup", "achievement", "fixture"])
async def test_simulation_fails_closed_on_incomplete_or_inconsistent_inputs(failure):
    request, repo, events, rules, simulation = context()
    if failure == "missing_version":
        rules._version = None
    elif failure == "inactive":
        rules._version = replace(rules._version, is_active=False)
    elif failure == "missing_event":
        events._events.pop()
    elif failure == "baseline":
        rows = json.loads(repo.capture_result.scores_json)
        rows[0]["final_points"] += 1
        repo.capture_result = replace(repo.capture_result, scores_json=canonical(rows))
    elif failure == "rollup":
        rows = json.loads(repo.capture_result.rollups_json)
        rows[0]["total_pts"] += 1
        repo.capture_result = replace(repo.capture_result, rollups_json=canonical(rows))
    elif failure == "missing_rollup":
        repo.capture_result = replace(repo.capture_result, rollups_json="[]")
    elif failure == "achievement":
        repo.capture_result = replace(repo.capture_result, source_json=canonical({"rank_dependent_achievements": [12]}))
    else:
        request = replace(request, fixture_ids=(100, 999))
    with pytest.raises(ValueError):
        await simulation.execute(request, 1)
    assert not repo.applied and not events.upserted


@pytest.mark.anyio
async def test_publication_rechecks_full_manifest_and_is_idempotent_by_hash():
    request, repo, _, _, simulation = context()
    approved = await simulation.execute(request, 1)
    publish = PublishPositionCorrectionUseCase(repo, simulation)
    first = await publish.execute(approved)
    assert await publish.execute(approved) == first
    assert len(repo.applied) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("mutation", ["source", "engine"])
async def test_publication_rejects_changed_source_or_engine_before_mutation(mutation):
    request, repo, _, _, simulation = context()
    approved = await simulation.execute(request, 1)
    repo.capture_result = replace(repo.capture_result, **({"source_json": canonical({
        "rank_dependent_achievements": [], "sentinel": "changed"})} if mutation == "source" else {"engine_hash": "v2"}))
    with pytest.raises(ValueError, match="changed after approval"):
        await PublishPositionCorrectionUseCase(repo, simulation).execute(approved)
    assert repo.applied == []


@pytest.mark.anyio
async def test_reverted_batch_cannot_republish_and_reversion_requires_actor():
    request, repo, _, _, simulation = context()
    approved = await simulation.execute(request, 1)
    repo.result = PositionPublicationResult(approved.batch_id, "reverted", 2, 1)
    with pytest.raises(ValueError, match="reverted"):
        await PublishPositionCorrectionUseCase(repo, simulation).execute(approved)
    revert = RevertPositionCorrectionUseCase(repo)
    with pytest.raises(ValueError):
        await revert.execute(approved.batch_id, " ")
    assert (await revert.execute(approved.batch_id, "reviewer")).status == "reverted"
    assert repo.reverted == [(approved.batch_id, "reviewer")]


@pytest.mark.parametrize("update", [{"fixture_ids": ()}, {"fixture_ids": (100, 100)}, {"fixture_ids": (False,)},
                                    {"player_id": 0}, {"position": "Midfielder"}, {"source_ref": ""},
                                    {"accepted_at": "2026-10-19T12:00:00"}])
def test_correction_request_rejects_unbounded_identity_or_provenance(update):
    request, *_ = context()
    with pytest.raises(ValueError):
        replace(request, **update)
