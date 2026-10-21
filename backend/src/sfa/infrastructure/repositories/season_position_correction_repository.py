"""PostgreSQL adapter for one immutable, season-scoped correction journal."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import bindparam, text

from sfa.domain.player_positions.publication import PositionPublicationResult, canonical, digest
from sfa.domain.player_positions.evidence_policy import provider_claim_hash as _semantics
from sfa.infrastructure.position_correction_sql import PositionPublicationSQL, _EVENT_FIELDS

ROLLUP_FIELDS = ("total_pts", "achievement_bonus_pts", "breakdown")
TABLES = {"events": ("player_event_scores", _EVENT_FIELDS),
          "rollups": ("sfa_season_scores", ROLLUP_FIELDS),
          "bonuses": ("player_achievement_bonuses", ("final_bonus", "calculation_details")),
          "explanations": ("ranking_player_explanations", ("status",))}


def engine_hash():
    root = Path(__file__).parents[2]
    files = ["domain/scoring/event_engine.py", "domain/scoring/services.py", "domain/scoring/value_objects.py",
             "domain/scoring/pass_stats.py", "application/use_cases/calculate_achievement_bonuses.py",
             "application/use_cases/simulate_active_season_position_impact.py",
             "application/use_cases/prepare_season_position_correction.py",
             "application/use_cases/audit_active_season_positions.py",
             "application/use_cases/record_position_evidence.py",
             "domain/player_positions/evidence_policy.py", "domain/player_positions/services.py",
             "domain/player_positions/longitudinal.py", "domain/player_positions/club_season_audit.py",
             "domain/player_positions/publication.py", "infrastructure/position_transaction.py"]
    return hashlib.sha256(b"".join((root/name).read_bytes() for name in files)).hexdigest()


def _authorities(values):
    groups = {}
    for item in values:
        if item.get('authority') == 'api-football-direct-validated':
            groups.setdefault((item['fixture_id'], item['team_id']), []).append(item)
    result = {}
    for key, entries in groups.items():
        latest = max(datetime.fromisoformat(i['fetched_at']) for i in entries)
        newest = [i for i in entries if datetime.fromisoformat(i['fetched_at']) == latest]
        if len({_semantics(i['payload']) for i in newest}) != 1:
            raise ValueError('Equal-time incompatible provider revisions require quarantine')
        result[key] = min(newest, key=canonical)
    return result


class SeasonPositionCorrectionRepository(PositionPublicationSQL):
    def __init__(self, session, recorder, events):
        super().__init__(session)
        self._recorder = recorder
        self._events = events

    def _filters(self, scope_json, version):
        scope = json.loads(scope_json)
        clauses, params = [], {"version": version, "scope": scope["key"]}
        for index, source in enumerate(scope["sources"]):
            params[f"season{index}"] = source["season"]
            # Scope is validated again here; identifiers are never interpolated from arbitrary SQL.
            comps = source["competition_ids"]
            if not comps or any(type(c) is not int or c <= 0 for c in comps):
                raise ValueError("Invalid competition scope")
            clauses.append(f"(x.season=:season{index} AND x.competition_id IN ({','.join(map(str, comps))}))")
        period = '('+' OR '.join(clauses)+')'
        fixture = f"SELECT x.id FROM fixtures x WHERE {period}"
        players = f"SELECT x.player_id FROM sfa_season_scores x WHERE {period} AND x.rules_version_id=:version"
        conditions = {
            "player_event_scores": period+" AND x.rules_version_id=:version",
            "sfa_season_scores": period+" AND x.rules_version_id=:version",
            "fixtures": period, "player_stats": f"x.fixture_id IN ({fixture})",
            "player_events": f"x.fixture_id IN ({fixture})",
            "fixture_team_strengths": f"x.fixture_id IN ({fixture})",
            "players": f"x.id IN ({players})", "player_position_assignments": f"x.player_id IN ({players})",
            "fixture_lineup_snapshots": f"x.fixture_id IN ({fixture})",
            "player_position_evidence": f"x.fixture_id IN ({fixture}) OR x.player_id IN ({players})",
            "position_lineup_arbitrations": f"x.fixture_id IN ({fixture})",
            "position_scope_classifications": "x.scope_key=:scope",
            "position_correction_batches": "true",
            "competition_achievements": period,
            "player_achievement_bonuses": period+" AND x.rules_version_id=:version",
            "individual_honors": "x.scope_key=:scope AND x.rules_version_id=:version",
            "scoring_rules_versions": "x.id=:version OR x.is_active",
            "competitions": "true", "teams": "true", "competition_stages": "true",
        }
        return conditions, params

    async def fingerprint(self, scope_json, rules_version_id):
        conditions, params = self._filters(scope_json, rules_version_id)
        result = {}
        for table, where in conditions.items():
            order = ("x.fixture_id,x.team_id" if table == "fixture_team_strengths" else
                     "x.batch_id" if table == "position_correction_batches" else "x.id")
            row = (await self._session.execute(text(
                f"SELECT count(*),md5(coalesce(string_agg(md5(to_jsonb(x)::text),'' ORDER BY {order}),'')) "
                f"FROM {table} x WHERE {where}"), params)).one()
            result[table] = list(row)
        result["engine"] = engine_hash()
        result['sql_functions'] = [list(r) for r in (await self._session.execute(text("""
            SELECT p.proname,md5(pg_get_functiondef(p.oid)) FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public'
             AND (p.proname LIKE 'sfa_%' OR p.proname LIKE '%position%'
               OR p.proname LIKE '%reviewed%' OR p.proname LIKE '%curated%') ORDER BY p.proname,p.oid
        """))).tuples()]
        result['active_view'] = await self._session.scalar(text("SELECT md5(pg_get_viewdef('position_active_lineup_snapshots'::regclass))"))
        return digest(result)

    async def validate_snapshot(self, snapshot):
        """Value equality, including complete row sets, in the same snapshot as fingerprint()."""
        conditions, params = self._filters(canonical(snapshot["scope"]), snapshot["version"])
        keys = {"scores": "player_event_scores", "rollups": "sfa_season_scores", "stats": "player_stats",
                "fixtures": "fixtures", "players": "players", "snapshots": "fixture_lineup_snapshots",
                "assignments": "player_position_assignments", "achievements": "competition_achievements",
                "bonuses": "player_achievement_bonuses", "honors": "individual_honors", "teams": "teams",
                "competitions": "competitions", "rules": "scoring_rules_versions"}
        if 'lineup_arbitrations' in snapshot:
            keys['lineup_arbitrations']='position_lineup_arbitrations'
        if 'scope_classifications' in snapshot:
            keys['scope_classifications']='position_scope_classifications'
        if 'published_corrections' in snapshot:
            actual = list((await self._session.execute(text(
                "SELECT jsonb_build_object('batch_id',batch_id,'status',status,'published_at',published_at,"
                "'rules_version_id',guard_rules_version_id,'after_image',after_image) "
                "FROM position_correction_batches ORDER BY published_at,batch_id"))).scalars())
            if canonical(actual) != canonical(snapshot['published_corrections']):
                raise ValueError('Frozen capture no longer matches published correction journals')
        for key, table in keys.items():
            values = sorted(snapshot[key], key=lambda r: r['id'])
            # Expanding migration columns are not a change to a pre-migration input image.
            extras = []
            if values:
                row = await self._session.scalar(text(f"SELECT to_jsonb(x) FROM {table} x LIMIT 1"))
                extras = sorted(set(row or {}) - set(values[0]))
            actual = await self._session.scalar(text(
                f"SELECT coalesce(jsonb_agg(to_jsonb(x)-CAST(:extras AS text[]) ORDER BY x.id),'[]')"
                f"=CAST(:expected AS jsonb) FROM {table} x WHERE {conditions[table]}"),
                params | {"expected": canonical(values), "extras": extras})
            if not actual:
                raise ValueError(f"Frozen capture no longer matches database input {table}")
        # Raw DTOs include the exact ELO, stage/config and player context consumed
        # by the engine. Comparing them closes gaps left by row-only score CAS.
        raw = []
        for source in snapshot['scope']['sources']:
            for comp in source['competition_ids']:
                raw.extend(await self._events.get_events_for_recalc(source['season'], comp, None, None))
        actual_raw = json.loads(json.dumps([asdict(r) for r in sorted(raw, key=lambda r:r.event_id)], default=str))
        if actual_raw != sorted(snapshot['raw_events'], key=lambda r:r['event_id']):
            raise ValueError('Frozen capture no longer matches raw scoring context')

    async def published(self, batch_id):
        row = (await self._session.execute(text(
            "SELECT status,manifest FROM position_correction_batches WHERE batch_id=:id"), {"id": batch_id})).first()
        if not row:
            return None
        return PositionPublicationResult(batch_id, row[0], len(json.loads(row[1]["event_changes_json"])),
                                         len(json.loads(row[1]["rollup_changes_json"])))

    async def _replace_many(self, table, changes, fields):
        if not changes:
            return
        sets = ','.join(f"{field}=(jsonb_populate_record(NULL::{table},p->'after')).{field}" for field in fields)
        changed = (await self._session.execute(text(
            f"UPDATE {table} t SET {sets} FROM jsonb_array_elements(CAST(:changes AS jsonb)) p "
            "WHERE t.id=(p->'before'->>'id')::bigint AND to_jsonb(t)=p->'before' RETURNING t.id"),
            {"changes": canonical(changes)})).scalars().all()
        if len(changed) != len(changes):
            raise ValueError(f"CAS value/set mismatch in {table}; roll back entire batch")

    async def _import_evidence(self, values):
        contexts = _authorities(values)
        for item in sorted(values, key=lambda i: i.get('fetched_at', i['received_at'])):
            fixture = (await self._session.execute(text(
                "SELECT external_id FROM fixtures WHERE id=:id"), {"id": item["fixture_id"]})).scalar_one()
            payload = {"fixture": {"external_id": fixture}, "lineups": [item["payload"]]}
            await self._recorder.execute(fixture, canonical(payload), item.get("source_ref", "retained-capture"),
                                   item["received_at"])
        for (fixture, team), item in contexts.items():
            versions = await self._rows("fixture_lineup_snapshots", "fixture_id=:fixture AND team_id=:team",
                                        {"fixture": fixture, "team": team})
            compatible = [v["id"] for v in versions if _semantics(v["payload"]) == _semantics(item["payload"])]
            authority = next(v["id"] for v in versions if v["payload_hash"] == digest(item["payload"]))
            revision = digest({"fixture": fixture, "team": team, "authority": item["payload_hash"],
                               "fetched_at": item["fetched_at"]})
            await self._session.execute(text("""
                INSERT INTO position_lineup_arbitrations(fixture_id,team_id,active_snapshot_id,compatible_snapshot_ids,
                    revision_id,source_ref,fetched_at,supersedes,reason,actor)
                VALUES(:fixture,:team,:active,:compatible,:revision,:source,:at,CAST(:supersedes AS jsonb),:reason,:actor)
                ON CONFLICT(revision_id) DO NOTHING
            """), {"fixture": fixture, "team": team, "active": authority, "compatible": compatible,
                    "revision": revision, "source": item.get("source_ref", "")+"#"+item["payload_hash"],
                    "at": datetime.fromisoformat(item["fetched_at"]),
                    "supersedes": canonical([v["id"] for v in versions if v["id"] not in compatible]),
                    "reason": "latest_validated_direct_provider_revision", "actor": "curated-season-pilot"})

    async def _validate_decision_evidence(self, decision):
        rows = await self._rows("player_position_evidence", "player_id=:player "
                                "AND fixture_id IN :fixtures AND lineup_snapshot_id IN "
                                "(SELECT id FROM position_active_lineup_snapshots)",
                                {"player": decision["player_id"], "team": decision["team_id"],
                                 "fixtures": tuple(decision["fixture_ids"])}, expanding=("fixtures",))
        if {r["fixture_id"] for r in rows} != set(decision["fixture_ids"]) or any(
            r['team_id'] != decision['team_id'] or r["assertion_kind"] != "starting_slot" or r["position"] != decision["position"]
            or not r["details"].get("valid_start_identity") or r["details"].get("issue") for r in rows
        ):
            raise ValueError("Durable active evidence does not support every curated fixture")
        return sorted({r["id"] for r in rows})

    async def _image_for(self, images):
        result = {}
        all_tables = TABLES | {"assignments": ("player_position_assignments", ()),
                              "classifications": ("position_scope_classifications", ())}
        for key, (table, _) in all_tables.items():
            ids = tuple(r["id"] for r in images.get(key, []))
            result[key] = await self._rows(table, "id IN :ids", {"ids": ids}, expanding=("ids",)) if ids else []
        return result

    async def apply(self, plan):
        self._exclusive()
        if engine_hash() != plan.engine_hash:
            raise ValueError("Prepared plan uses a different scoring/compiler engine")
        await self._session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
        await self._import_evidence(json.loads(plan.evidence_json))
        decisions = json.loads(plan.decisions_json)
        evidence_ids = {d["player_id"]: await self._validate_decision_evidence(d) for d in decisions}
        changes = {"events": json.loads(plan.event_changes_json), "rollups": json.loads(plan.rollup_changes_json),
                   "bonuses": json.loads(plan.bonus_changes_json)}
        scope = json.loads(plan.scope_json)
        comps = sorted(c for source in scope["sources"] for c in source["competition_ids"])
        explanations = await self._rows("ranking_player_explanations", "rules_version_id=:version "
                                        "AND scope<>'world_cup' AND (season='2026' OR scope='all_time') "
                                        "AND (competition_id IS NULL OR competition_id IN :comps)",
                                        {"version": plan.rules_version_id, "comps": tuple(comps)}, expanding=("comps",))
        changes["explanations"] = [{"before": e, "after": dict(e, status="stale")} for e in explanations]
        before = {key: [c["before"] for c in values] for key, values in changes.items()}
        before.update(assignments=[], classifications=[])
        await self._session.execute(text("""
            INSERT INTO position_correction_batches(batch_id,manifest_hash,manifest,before_image,after_image,status,actor)
            VALUES(:id,:id,CAST(:manifest AS jsonb),CAST(:before AS jsonb),'{}','published',:actor)
        """), {"id": plan.batch_id, "manifest": canonical(asdict(plan)), "before": canonical(before), "actor": plan.actor})
        for key, (table, fields) in TABLES.items():
            await self._replace_many(table, changes[key], fields)
            if key == "events" and self._session.info.get("position_publication_failpoint"):
                raise RuntimeError("Intentional season publication failpoint after events")
        assignments = []
        for decision in decisions:
            start = await self._session.scalar(text("SELECT min(played_at) FROM fixtures WHERE id IN :ids")
                                               .bindparams(bindparam("ids", expanding=True)),
                                               {"ids": tuple(decision["fixture_ids"])})
            row = (await self._session.execute(text("""
                INSERT INTO player_position_assignments(player_id,team_id,season,position,status,effective_from,
                    effective_until,revision_id,evidence_ids,source_kind,reason,actor,applicable_fixture_ids,
                    assertion_kind,source_ref,decision_policy,publication_batch_id)
                VALUES(:player,:team,:season,:position,'accepted',:start,:end,:revision,CAST(:evidence AS jsonb),
                    'curated_scoring_decision',:reason,:actor,:fixtures,'curated_fixture_scoring_role',:source,:policy,:batch)
                RETURNING to_jsonb(player_position_assignments)
            """), {"player": decision["player_id"], "team": decision["team_id"], "season": decision["season"],
                    "position": decision["position"], "start": start, "end": datetime.fromisoformat(plan.accepted_at),
                    "revision": decision["decision_id"], "evidence": canonical(evidence_ids[decision["player_id"]]),
                    "reason": decision["statement"], "actor": plan.actor, "fixtures": decision["fixture_ids"],
                    "source": decision["source_ref"], "policy": decision["policy"], "batch": plan.batch_id})).scalar_one()
            assignments.append(row)
        classifications = []
        for definition in json.loads(plan.classifications_json):
            row = (await self._session.execute(text("""
                INSERT INTO position_scope_classifications(player_id,team_id,scope_key,position,competition_ids,
                    scope_competition_ids,decision_id,definition,batch_id)
                VALUES(:player,:team,:scope,:position,:comps,:scope_comps,:decision,CAST(:definition AS jsonb),:batch)
                RETURNING to_jsonb(position_scope_classifications)
            """), {"player": definition["player_id"], "team": definition["team_id"], "scope": definition["scope_key"],
                    "position": definition["position"], "comps": definition["competition_ids"],
                    "scope_comps": definition["scope_competition_ids"], "decision": definition["decision_id"],
                    "definition": canonical(definition), "batch": plan.batch_id})).scalar_one()
            classifications.append(row)
        expected = {key: [c["after"] for c in values] for key, values in changes.items()}
        expected.update(assignments=assignments, classifications=classifications)
        after = await self._image_for(expected)
        await self._session.execute(text("UPDATE position_correction_batches SET after_image=CAST(:after AS jsonb) "
                                         "WHERE batch_id=:id"), {"after": canonical(after), "id": plan.batch_id})
        await self._session.execute(text("UPDATE position_publication_epoch SET revision=revision+1"))
        return PositionPublicationResult(plan.batch_id, "published", len(changes["events"]), len(changes["rollups"]))

    async def revert(self, batch_id, actor):
        self._exclusive()
        row = (await self._session.execute(text("SELECT * FROM position_correction_batches WHERE batch_id=:id"),
                                           {"id": batch_id})).mappings().one()
        if row["status"] == "reverted":
            return PositionPublicationResult(batch_id, "reverted", 0, 0)
        before, after = row["before_image"], row["after_image"]
        if await self._image_for(after) != after:
            raise ValueError("Postimages changed after publication; a new compensation is required")
        await self._session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
        for key, (table, fields) in TABLES.items():
            old = {r["id"]: r for r in before[key]}
            await self._replace_many(table, [{"before": r, "after": old[r["id"]]} for r in after[key]], fields)
        for assignment in after["assignments"]:
            await self._replace_row("player_position_assignments", assignment,
                                    dict(assignment, status="superseded"), ("status",))
        # Classification rows remain immutable history; their batch status
        # removes them from every projection atomically with compensation.
        await self._session.execute(text("UPDATE position_correction_batches SET status='reverted',reverted_at=now(),reverted_by=:actor "
                                         "WHERE batch_id=:id"), {"id": batch_id, 'actor': actor})
        await self._session.execute(text("UPDATE position_publication_epoch SET revision=revision+1"))
        return PositionPublicationResult(batch_id, "reverted", len(after["events"]), len(after["rollups"]))
