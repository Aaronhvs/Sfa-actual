from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import bindparam, text

from sfa.domain.player_positions.ports import PositionCorrectionRepository
from sfa.domain.player_positions.publication import (
    PositionCorrectionCapture,
    PositionCorrectionPlan,
    PositionCorrectionRequest,
    PositionPublicationResult,
    canonical,
    digest,
)

from sfa.infrastructure.position_correction_sql import PositionPublicationSQL, _EVENT_FIELDS, _ROLLUP_FIELDS


class PostgreSQLPositionCorrectionRepository(PositionPublicationSQL, PositionCorrectionRepository):
    async def capture(self, request: PositionCorrectionRequest, rules_version_id: int) -> PositionCorrectionCapture:
        params = {"player": request.player_id, "team": request.team_id, "season": request.season,
                  "fixtures": request.fixture_ids, "version": rules_version_id}
        player = await self._rows("players", "id=:player", params)
        team = await self._rows("teams", "id=:team", params)
        if not player or player[0]["external_id"] != request.external_player_id or not team or \
                team[0]["external_id"] != request.external_team_id:
            raise ValueError("Curated player/team crosswalk changed or does not exist")
        fixtures = await self._rows("fixtures", "id IN :fixtures", params, expanding=("fixtures",))
        accepted_at = datetime.fromisoformat(request.accepted_at)
        if len(fixtures) != len(request.fixture_ids) or any(
            f["season"] != request.season or request.team_id not in (f["home_team_id"], f["away_team_id"])
            or f["status"] not in {"FT", "AET", "PEN"}
            or datetime.fromisoformat(f["played_at"]) >= accepted_at for f in fixtures
        ):
            raise ValueError("Correction fixture context/status/date does not match the approved scope")
        evidence = await self._rows("player_position_evidence", "player_id=:player AND fixture_id IN :fixtures "
                                    "AND lineup_snapshot_id IN (SELECT id FROM position_active_lineup_snapshots) "
                                    "AND assertion_kind IN "
                                    "('starting_slot','starting_participation','bench_membership')",
                                    params, expanding=("fixtures",))
        if {e["fixture_id"] for e in evidence} != set(request.fixture_ids) or any(
            e["team_id"] != request.team_id or e["season"] != request.season or e["position"] != request.position
            or e["assertion_kind"] != "starting_slot"
            or not e["details"].get("valid_start_identity") or e["details"].get("issue") for e in evidence
        ):
            raise ValueError("Missing, ambiguous or contradictory starting evidence in curated historical scope")
        snapshots = await self._rows("position_active_lineup_snapshots", "fixture_id IN :fixtures AND team_id=:team",
                                    params, expanding=("fixtures",))
        # Different normalized provider snapshots must agree on this player's claim.
        if (not snapshots or any(s["validation_status"] != "interpreted" for s in snapshots)
                or any(e["lineup_snapshot_id"] not in {s["id"] for s in snapshots} for e in evidence)):
            raise ValueError("Starting evidence has no retained source snapshot")
        proofs = await self._rows("position_source_coverage", "scope_key IN :keys",
                                  {"keys": tuple(f"fixture:{f['external_id']}" for f in fixtures)}, expanding=("keys",))
        arbitrations = await self._rows('position_lineup_arbitrations', 'fixture_id IN :fixtures', params,
                                       expanding=('fixtures',))
        arbitrated = {a['fixture_id'] for a in arbitrations}
        if any(p["proof"].get("conflicting_lineup_versions") and not any(
                p['scope_key'] == f"fixture:{f['external_id']}" and f['id'] in arbitrated for f in fixtures) for p in proofs):
            raise ValueError("Retained lineup versions conflict; curate the source discrepancy before publishing")
        competitions = tuple(sorted({f["competition_id"] for f in fixtures}))
        params["competitions"] = competitions
        scope = "season=:season AND competition_id IN :competitions"
        source = {
            "player": player, "team": team, "fixtures": fixtures, "evidence": evidence, "snapshots": snapshots,
            "lineup_proofs": proofs,
            "assignments": await self._rows("player_position_assignments", "player_id=:player", params),
            "raw_events": await self._rows("player_events", "player_id=:player AND fixture_id IN "
                "(SELECT id FROM fixtures WHERE season=:season)", params),
            "raw_stats": await self._rows("player_stats", "player_id=:player AND fixture_id IN "
                "(SELECT id FROM fixtures WHERE season=:season)", params),
            "elo": await self._rows("fixture_team_strengths", "fixture_id IN "
                "(SELECT fixture_id FROM player_events e JOIN fixtures f ON f.id=e.fixture_id "
                "WHERE e.player_id=:player AND f.season=:season)", params),
            "rank_dependent_achievements": await self._rows("competition_achievements",
                scope + " AND team_id=:team", params, expanding=("competitions",)),
            "bonuses": await self._rows("player_achievement_bonuses",
                scope + " AND team_id=:team AND rules_version_id=:version", params, expanding=("competitions",)),
            "honors": await self._rows("individual_honors", "source_season=:season AND rules_version_id=:version",
                                       params),
            "explanations": await self._rows("ranking_player_explanations", "rules_version_id=:version", params),
        }
        scores = await self._rows("player_event_scores",
                                  "player_id=:player AND season=:season AND rules_version_id=:version", params)
        rollups = await self._rows("sfa_season_scores",
                                   "player_id=:player AND season=:season AND rules_version_id=:version", params)
        engine_files = Path(__file__).parents[2] / "domain" / "scoring"
        engine_hash = hashlib.sha256(b"".join((engine_files / name).read_bytes() for name in (
            "event_engine.py", "services.py", "value_objects.py", "pass_stats.py"))).hexdigest()
        return PositionCorrectionCapture(canonical(source), canonical(scores), canonical(rollups), engine_hash)

    async def published(self, batch_id: str) -> PositionPublicationResult | None:
        row = (await self._session.execute(text(
            "SELECT batch_id,status,manifest FROM position_correction_batches WHERE batch_id=:id"
        ), {"id": batch_id})).mappings().first()
        if row is None:
            return None
        plan = row["manifest"]
        return PositionPublicationResult(batch_id, row["status"], len(json.loads(plan["event_changes_json"])),
                                         len(json.loads(plan["rollup_changes_json"])))

    async def _assignment(self, plan, source, *, historical):
        request = plan.request
        reference = json.loads(request.current_reference_json) if not historical and request.current_reference_json else None
        ref = request.source_ref + (":historical-fixtures" if historical else ":current-habitual")
        revision = digest({"batch": plan.batch_id, "historical": historical})
        start = min(f["played_at"] for f in source["fixtures"]) if historical else request.accepted_at
        params = {"player": request.player_id, "team": request.team_id, "season": request.season,
                  "position": request.position, "start": datetime.fromisoformat(start),
                  "end": datetime.fromisoformat(request.accepted_at) if historical else None,
                  "revision": revision, "evidence": canonical([e["id"] for e in source["evidence"]]),
                  "source": ref, "reason": request.statement, "actor": request.actor,
                  "fixtures": list(request.fixture_ids) if historical else None, "batch": plan.batch_id,
                  "kind": ("curated_fixture_scoring_role" if historical and request.schema_version == 2
                           else "habitual_football_role")}
        if reference:
            params.update(position=reference["position"], source=reference["source_ref"], reason=reference["statement"],
                          start=datetime.fromisoformat(reference["accepted_at"]), evidence=canonical(reference["evidence_ids"]))
        return await self._session.scalar(text("""
            INSERT INTO player_position_assignments
              (player_id,team_id,season,position,tactical_role,side,status,effective_from,effective_until,
               revision_id,evidence_ids,source_kind,reason,actor,applicable_fixture_ids,assertion_kind,
               source_ref,decision_policy,publication_batch_id)
            VALUES(:player,:team,:season,:position,NULL,NULL,'accepted',:start,:end,:revision,
                   CAST(:evidence AS jsonb),'curated_user_decision',:reason,:actor,:fixtures,
                   :kind,:source,'curated-fixture-evidence-v2',:batch) RETURNING id
        """), params)

    async def _image(self, event_ids, rollup_ids, assignment_ids, explanation_ids):
        image = {}
        for key, table, ids in (("events", "player_event_scores", event_ids),
                                ("rollups", "sfa_season_scores", rollup_ids),
                                ("assignments", "player_position_assignments", assignment_ids),
                                ("explanations", "ranking_player_explanations", explanation_ids)):
            image[key] = await self._rows(table, "id IN :ids", {"ids": tuple(ids)}, expanding=("ids",)) if ids else []
        return image

    async def apply(self, plan: PositionCorrectionPlan) -> PositionPublicationResult:
        self._exclusive()
        await self._session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
        changes, rollups = json.loads(plan.event_changes_json), json.loads(plan.rollup_changes_json)
        source = json.loads(plan.dependencies_json)["source"]
        before_image = {"events": [c["before"] for c in changes], "rollups": [c["before"] for c in rollups],
                        "assignments": [], "explanations": source["explanations"]}
        for index, change in enumerate(changes):
            await self._replace_row("player_event_scores", change["before"], change["after"], _EVENT_FIELDS)
            if index == 0 and self._session.info.get("position_publication_failpoint") == "after_first_score":
                raise RuntimeError("Intentional publication failpoint after first score")
        for change in rollups:
            await self._replace_row("sfa_season_scores", change["before"], change["after"], _ROLLUP_FIELDS)
        assignment_ids = [await self._assignment(plan, source, historical=True)]
        if plan.request.schema_version == 1 or plan.request.current_reference_json:
            assignment_ids.append(await self._assignment(plan, source, historical=False))
        for row in source["explanations"]:
            await self._replace_row("ranking_player_explanations", row, dict(row, status="stale"), ("status",))
        after_image = await self._image([r["before"]["id"] for r in changes],
                                        [r["before"]["id"] for r in rollups], assignment_ids,
                                        [r["id"] for r in source["explanations"]])
        await self._session.execute(text("""
            INSERT INTO position_correction_batches
              (batch_id,manifest_hash,manifest,before_image,after_image,status,actor)
            VALUES(:id,:id,CAST(:manifest AS jsonb),CAST(:before AS jsonb),CAST(:after AS jsonb),'published',:actor)
        """), {"id": plan.batch_id, "manifest": canonical(asdict(plan)), "before": canonical(before_image),
               "after": canonical(after_image), "actor": plan.request.actor})
        await self._session.execute(text("UPDATE position_publication_epoch SET revision=revision+1"))
        return PositionPublicationResult(plan.batch_id, "published", len(changes), len(rollups))

    async def revert(self, batch_id: str, actor: str) -> PositionPublicationResult:
        self._exclusive()
        row = (await self._session.execute(text("SELECT * FROM position_correction_batches WHERE batch_id=:id"),
                                           {"id": batch_id})).mappings().first()
        if row is None:
            raise ValueError("Correction batch not found")
        if row["status"] == "reverted":
            return PositionPublicationResult(batch_id, "reverted", 0, 0)
        before, after = row["before_image"], row["after_image"]
        actual = await self._image([r["id"] for r in after["events"]], [r["id"] for r in after["rollups"]],
                                   [r["id"] for r in after["assignments"]], [r["id"] for r in after["explanations"]])
        if actual != after:
            raise ValueError("Published records changed afterwards; reversion requires a new reviewed compensation")
        await self._session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
        for key, table, fields in (("events", "player_event_scores", _EVENT_FIELDS),
                                    ("rollups", "sfa_season_scores", _ROLLUP_FIELDS),
                                    ("explanations", "ranking_player_explanations", ("status",))):
            old_by_id = {r["id"]: r for r in before[key]}
            for image in after[key]:
                await self._replace_row(table, image, old_by_id[image["id"]], fields)
        # Keep assignment history as superseded; do not erase accepted decisions/journal.
        for assignment in after["assignments"]:
            await self._replace_row("player_position_assignments", assignment,
                                    dict(assignment, status="superseded"), ("status",))
        await self._session.execute(text("UPDATE position_correction_batches SET status='reverted',reverted_at=now(),"
                                         "actor=actor||' / reverted by '||:actor WHERE batch_id=:id"),
                                    {"id": batch_id, "actor": actor})
        await self._session.execute(text("UPDATE position_publication_epoch SET revision=revision+1"))
        return PositionPublicationResult(batch_id, "reverted", len(after["events"]), len(after["rollups"]))
