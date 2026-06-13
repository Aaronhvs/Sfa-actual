from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class SFASeasonScore(Base):
    __tablename__ = "sfa_season_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id"), nullable=False
    )
    # ALTER TABLE sfa_season_scores ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;
    # CREATE INDEX IF NOT EXISTS ix_sfa_season_scores_team_id ON sfa_season_scores(team_id);
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    # NULL = legacy score (pre-versioning). NOT NULL = score under a specific rules version.
    rules_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("scoring_rules_versions.id"), nullable=True
    )
    total_pts: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # achievement_bonus_pts: sum of all PlayerAchievementBonus for this player/comp/season/version
    achievement_bonus_pts: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    matches_played: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_updated: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # NOTE: the old UniqueConstraint "uq_sfa_season_score" is dropped in migration 0012.
        # Uniqueness enforced via two partial indexes:
        #   uq_sfa_season_score_legacy    WHERE rules_version_id IS NULL
        #   uq_sfa_season_score_versioned WHERE rules_version_id IS NOT NULL
        CheckConstraint("matches_played >= 0", name="ck_score_matches_played"),
        CheckConstraint("achievement_bonus_pts >= 0", name="ck_score_achievement_bonus_positive"),
    )
