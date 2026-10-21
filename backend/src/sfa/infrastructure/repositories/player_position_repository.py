from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from sfa.domain.player_position_overrides import position_for_context
from sfa.domain.player_positions.ports import (
    DurableLineupCapture,
    PositionFixtureContext,
    PositionIdentityRecord,
    RecordPositionEvidenceResult,
)
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_positions.models import (
    FixtureLineupSnapshot,
    PlayerPositionAssignment,
    PlayerPositionEvidence,
    PositionSourceCoverage,
)
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.teams.models import Team


class PlayerPositionRepository:
    """Evidence adapter; the input adapter owns its transaction and commit."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def identity(self, player_id: int) -> PositionIdentityRecord | None:
        row = (await self._session.execute(select(
            Player.id, Player.external_id, Player.position, Player.position_source, Player.name,
        ).where(Player.id == player_id))).one_or_none()
        if row is None:
            return None
        stored = row[2].value
        # Migration comparison only: a legacy name override is not new sporting evidence.
        effective = position_for_context(stored, player_name=row[4])
        return PositionIdentityRecord(row[0], row[1], stored, row[3], effective)

    async def accept_reference(
        self, player_id: int, position: str, revision_id: str, source_ref: str, statement: str,
        accepted_at: str, actor: str,
        decision_status: str,
    ) -> bool:
        details = {"assertion_kind": "habitual_football_role", "statement": statement,
                   "scope": "current_habitual_reference", "retroactive_effect": False,
                   "identity": "validated_internal_external_pair"}
        evidence_id = (await self._session.execute(insert(PlayerPositionEvidence).values(
            player_id=player_id, assertion_kind="habitual_football_role", position=position,
            source_ref=source_ref, source_hash=revision_id, details=details,
            observed_at=datetime.fromisoformat(accepted_at),
        ).on_conflict_do_nothing().returning(PlayerPositionEvidence.id))).scalar_one_or_none()
        if evidence_id is None:
            evidence_id = (await self._session.execute(select(PlayerPositionEvidence.id).where(
                PlayerPositionEvidence.player_id == player_id,
                PlayerPositionEvidence.assertion_kind == "habitual_football_role",
                PlayerPositionEvidence.source_hash == revision_id,
            ))).scalar_one()
        assignment_id = (await self._session.execute(insert(PlayerPositionAssignment).values(
            player_id=player_id, position=position, status=decision_status, revision_id=revision_id,
            effective_from=datetime.fromisoformat(accepted_at), evidence_ids=[evidence_id],
            source_kind="user_confirmation", reason=statement, actor=actor,
            secondaries=[], created_at=datetime.fromisoformat(accepted_at),
        ).on_conflict_do_nothing(index_elements=["revision_id"]).returning(
            PlayerPositionAssignment.id,
        ))).scalar_one_or_none()
        return assignment_id is not None

    async def coverage_inventory(self, competition_id: int, season: str) -> str:
        rows = (await self._session.execute(text("""
            SELECT f.external_id, h.external_id home_team_external_id, a.external_id away_team_external_id,
                   f.status, coalesce(latest.proof->>'both_starting_elevens'='true'
                     AND jsonb_array_length(coalesce(latest.proof->'unresolved_starting_player_ids',
                                                     latest.proof->'unresolved_player_ids','[]'))=0
                     AND coalesce(latest.proof->>'unresolved_starting_identity',
                                  latest.proof->>'unresolved_missing_identity','false')='false'
                     AND coalesce(latest.proof->>'conflicting_lineup_versions','false')='false',false)
                     both_starting_elevens
            FROM fixtures f JOIN teams h ON h.id=f.home_team_id JOIN teams a ON a.id=f.away_team_id
            LEFT JOIN LATERAL (
              SELECT proof FROM position_source_coverage c WHERE c.scope_key='fixture:'||f.external_id::text
              ORDER BY c.id DESC LIMIT 1
            ) latest ON true
            WHERE f.competition_id=:competition AND f.season=:season ORDER BY f.external_id
        """), {"competition": competition_id, "season": season})).mappings().all()
        return json.dumps([dict(row) for row in rows])

    async def record_calendar(self, scope_key: str, proof_json: str, status: str) -> None:
        await self._session.execute(insert(PositionSourceCoverage).values(
            scope_key=scope_key, proof_hash=hashlib.sha256(proof_json.encode()).hexdigest(),
            proof=json.loads(proof_json), status=status, observed_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing())

    async def calendar_scope_due(self, league_id: int, season: str) -> bool:
        return not bool(await self._session.scalar(text("""
            SELECT EXISTS(SELECT 1 FROM position_source_coverage
              WHERE scope_key=:scope AND observed_at>now()-interval '1 day')
        """), {"scope": f"calendar:{league_id}:{season}"}))

    async def competition_id_for_name(self, name: str) -> int | None:
        from sfa.infrastructure.models.competitions.models import Competition
        return await self._session.scalar(select(Competition.id).where(Competition.name == name))

    async def pending_lineups(self, season: str, limit: int) -> tuple[int, ...]:
        rows = await self._session.execute(text("""
            SELECT f.external_id FROM fixtures f
            LEFT JOIN LATERAL (
              SELECT proof FROM position_source_coverage c WHERE c.scope_key='fixture:'||f.external_id::text
              ORDER BY c.id DESC LIMIT 1
            ) latest ON true
            WHERE f.season=:season AND f.status IN ('FT','AET','PEN') AND f.played_at<=now()
              AND (coalesce(latest.proof->>'both_starting_elevens','false')!='true'
                OR jsonb_array_length(coalesce(latest.proof->'unresolved_starting_player_ids',
                                               latest.proof->'unresolved_player_ids','[]'))>0
                OR coalesce(latest.proof->>'unresolved_starting_identity',
                            latest.proof->>'unresolved_missing_identity','false')='true'
                OR coalesce(latest.proof->>'conflicting_lineup_versions','false')='true')
              AND NOT EXISTS (
                SELECT 1 FROM position_source_coverage c
                WHERE c.scope_key='lineup-request:'||f.external_id::text
                  AND c.observed_at>now()-interval '6 hours'
              )
            ORDER BY f.played_at DESC,f.id DESC LIMIT :limit
        """), {"season": season, "limit": limit})
        return tuple(rows.scalars())

    async def checkpoint_collection(self, fixture_id: int | None, state: str, details_json: str) -> None:
        proof = {"state": state, "details": json.loads(details_json)}
        serialized = json.dumps(proof, sort_keys=True, separators=(",", ":"))
        # Timestamp separates attempts while content hash identifies each durable record.
        now = datetime.now(timezone.utc)
        digest = hashlib.sha256((now.isoformat() + serialized).encode()).hexdigest()
        await self._session.execute(insert(PositionSourceCoverage).values(
            scope_key=f"lineup-request:{fixture_id or 'status'}", proof_hash=digest,
            proof=proof, status="partial", observed_at=now,
        ))

    async def get_fixture_context(self, external_id: int) -> PositionFixtureContext | None:
        home, away = aliased(Team), aliased(Team)
        session = self._session
        row = (await session.execute(
            select(Fixture, home.external_id, away.external_id)
            .join(home, home.id == Fixture.home_team_id).join(away, away.id == Fixture.away_team_id)
            .where(Fixture.external_id == external_id)
        )).first()
        if row is None:
            return None
        fixture = row[0]
        return PositionFixtureContext(
            fixture.id, fixture.external_id, fixture.competition_id, fixture.season,
            fixture.played_at.isoformat(),
            ((row[1], fixture.home_team_id), (row[2], fixture.away_team_id)),
        )

    async def get_player_ids(self, external_ids: tuple[int, ...]) -> dict[int, int]:
        if not external_ids:
            return {}
        session = self._session
        return dict((await session.execute(
            select(Player.external_id, Player.id).where(Player.external_id.in_(external_ids))
        )).all())

    async def record_lineups(
        self, context: PositionFixtureContext, captures: tuple[DurableLineupCapture, ...],
        source_ref: str, received_at: str, coverage_json: str,
    ) -> RecordPositionEvidenceResult:
        inserted_snapshots = inserted_evidence = 0
        session = self._session
        for capture in captures:
            statement = insert(FixtureLineupSnapshot).values(
                fixture_id=context.fixture_id, team_id=capture.team_id, provider="api-football",
                payload=json.loads(capture.payload_json), payload_hash=capture.payload_hash,
                source_ref=source_ref, received_at=datetime.fromisoformat(received_at),
                validation_status=capture.validation_status, validation_reason=capture.validation_reason,
                schema_version="api-football-grid-v3",
            ).on_conflict_do_nothing().returning(FixtureLineupSnapshot.id)
            snapshot_id = (await session.execute(statement)).scalar_one_or_none()
            if snapshot_id is not None:
                inserted_snapshots += 1
            else:
                snapshot_id = (await session.execute(select(FixtureLineupSnapshot.id).where(
                    FixtureLineupSnapshot.fixture_id == context.fixture_id,
                    FixtureLineupSnapshot.team_id == capture.team_id,
                    FixtureLineupSnapshot.provider == "api-football",
                    FixtureLineupSnapshot.payload_hash == capture.payload_hash,
                ))).scalar_one()
            values = [dict(
                player_id=evidence.player_id, lineup_snapshot_id=snapshot_id,
                fixture_id=context.fixture_id, team_id=capture.team_id,
                competition_id=context.competition_id, season=context.season,
                assertion_kind=evidence.assertion_kind, position=evidence.position,
                tactical_role=evidence.tactical_role, side=evidence.side,
                source_ref=source_ref, source_hash=evidence.source_hash,
                details=json.loads(evidence.details_json), observed_at=datetime.fromisoformat(received_at),
            ) for evidence in capture.evidence]
            if values:
                ids = (await session.execute(insert(PlayerPositionEvidence).values(values)
                    .on_conflict_do_nothing().returning(PlayerPositionEvidence.id))).scalars().all()
                inserted_evidence += len(ids)
        proof = json.loads(coverage_json)
        previous = (await session.execute(select(PositionSourceCoverage.proof).where(
            PositionSourceCoverage.scope_key == f"fixture:{context.external_id}",
        ))).scalars().all()
        fingerprints = proof.get("starting_identity_fingerprints", {})
        conflicting = any(old.get("conflicting_lineup_versions") or any(
            team in fingerprints and fingerprint != fingerprints[team]
            for team, fingerprint in old.get("starting_identity_fingerprints", {}).items()
        ) for old in previous)
        proof["conflicting_lineup_versions"] = conflicting
        if conflicting:
            proof["both_starting_elevens"] = False
        coverage_json = json.dumps(proof, sort_keys=True, separators=(",", ":"))
        await session.execute(insert(PositionSourceCoverage).values(
            scope_key=f"fixture:{context.external_id}",
            proof_hash=hashlib.sha256(coverage_json.encode()).hexdigest(), proof=proof,
            status=proof["status"], observed_at=datetime.fromisoformat(received_at),
        ).on_conflict_do_nothing())
        return RecordPositionEvidenceResult(context.external_id, inserted_snapshots, inserted_evidence, "recorded")
