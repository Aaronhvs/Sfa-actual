from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class IndividualHonorModel(Base):
    __tablename__ = "individual_honors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_label: Mapped[str] = mapped_column(String(100), nullable=False)
    context_key: Mapped[str] = mapped_column(String(100), nullable=False)
    context_label: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_category: Mapped[str] = mapped_column(String(40), nullable=False)
    honor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_season: Mapped[str] = mapped_column(String(10), nullable=False)
    competition_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitions.id"), nullable=True
    )
    rules_version_id: Mapped[int] = mapped_column(
        ForeignKey("scoring_rules_versions.id"), nullable=False
    )
    metric_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    metric_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metric_rate: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    raw_bonus_pts: Mapped[int] = mapped_column(Integer, nullable=False)
    awarded_bonus_pts: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index(
            "uq_individual_honor_context",
            "scope_key",
            "context_key",
            "honor_type",
            "rules_version_id",
            unique=True,
        ),
        Index("ix_individual_honors_player_scope", "player_id", "scope_key"),
        CheckConstraint("metric_value >= 0", name="ck_individual_honor_metric_value"),
        CheckConstraint("metric_total IS NULL OR metric_total >= 0", name="ck_individual_honor_metric_total"),
        CheckConstraint(
            "metric_rate IS NULL OR (metric_rate >= 0 AND metric_rate <= 1)",
            name="ck_individual_honor_metric_rate",
        ),
        CheckConstraint("raw_bonus_pts >= 0", name="ck_individual_honor_raw_bonus"),
        CheckConstraint(
            "awarded_bonus_pts >= 0 AND awarded_bonus_pts <= raw_bonus_pts",
            name="ck_individual_honor_awarded_bonus",
        ),
    )
