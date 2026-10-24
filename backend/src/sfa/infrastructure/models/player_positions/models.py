from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class FixtureLineupSnapshot(Base):
    __tablename__ = "fixture_lineup_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id", ondelete="RESTRICT"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    source_ref: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validation_status: Mapped[str] = mapped_column(String(30))
    validation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(60), default="api-football-grid-v3")
    __table_args__ = (UniqueConstraint("fixture_id", "team_id", "provider", "payload_hash"),)


class PositionSourceCoverage(Base):
    __tablename__ = "position_source_coverage"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(160))
    proof_hash: Mapped[str] = mapped_column(String(64))
    proof: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("scope_key", "proof_hash"),)


class PlayerPositionEvidence(Base):
    __tablename__ = "player_position_evidence"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    lineup_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("fixture_lineup_snapshots.id"), nullable=True)
    fixture_id: Mapped[int | None] = mapped_column(ForeignKey("fixtures.id"), nullable=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    competition_id: Mapped[int | None] = mapped_column(ForeignKey("competitions.id"), nullable=True)
    season: Mapped[str | None] = mapped_column(String(10), nullable=True)
    assertion_kind: Mapped[str] = mapped_column(String(40))
    position: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tactical_role: Mapped[str | None] = mapped_column(String(15), nullable=True)
    side: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_ref: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSONB)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("player_id", "assertion_kind", "source_hash"),)


class PlayerPositionAssignment(Base):
    __tablename__ = "player_position_assignments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    competition_id: Mapped[int | None] = mapped_column(ForeignKey("competitions.id"), nullable=True)
    season: Mapped[str | None] = mapped_column(String(10), nullable=True)
    position: Mapped[str] = mapped_column(String(10))
    tactical_role: Mapped[str | None] = mapped_column(String(15), nullable=True)
    side: Mapped[str | None] = mapped_column(String(10), nullable=True)
    secondaries: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision_id: Mapped[str] = mapped_column(String(64), unique=True)
    evidence_ids: Mapped[list] = mapped_column(JSONB, default=list)
    source_kind: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    applicable_fixture_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    assertion_kind: Mapped[str] = mapped_column(String(40), default="habitual_football_role")
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
