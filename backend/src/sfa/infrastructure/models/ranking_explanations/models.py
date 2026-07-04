from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class RankingPlayerExplanation(Base):
    __tablename__ = "ranking_player_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    competition_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=True
    )
    rules_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("scoring_rules_versions.id", ondelete="SET NULL"), nullable=True
    )
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    variant: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    short_text: Mapped[str] = mapped_column(Text, nullable=False)
    long_text: Mapped[str] = mapped_column(Text, nullable=False)
    bullets: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_ranking_player_expl_scope_rank",
            "season",
            "competition_id",
            "rules_version_id",
            "scope",
            "rank",
        ),
        Index("ix_ranking_player_expl_player_scope", "player_id", "season", "rules_version_id", "scope"),
        Index("ix_ranking_player_expl_status", "status"),
    )
