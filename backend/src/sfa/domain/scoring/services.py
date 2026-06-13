from __future__ import annotations

from .value_objects import (
    ActionType,
    CombinedMultiplier,
    M1RivalDifficulty,
    M2CompetitionStage,
    M3MinuteScore,
    M4ShotDifficulty,
    MratingFactor,
    MvisitFactor,
    PositionGroup,
    SFAScore,
    ScoringConfig,
)

# ---------------------------------------------------------------------------
# Base points table — Section 2 of the SFA business-logic document v2.0
# ---------------------------------------------------------------------------
# Entries with 0 pts mean the action does not apply to that position group.
# The table is the single source of truth; SFAScoringService never hard-codes
# points inline.
# ---------------------------------------------------------------------------

BASE_POINTS_TABLE: dict[PositionGroup, dict[ActionType, int]] = {
    PositionGroup.FW: {
        ActionType.GOAL: 500,
        ActionType.GOAL_PENALTY: 300,
        ActionType.GOAL_SHOOTOUT: 300,
        ActionType.ASSIST: 500,
        ActionType.CORNER_ASSIST: 250,
        ActionType.XG_NO_GOAL: 70,
        ActionType.XA_NO_ASSIST: 60,
        ActionType.DRIBBLES_WON: 100,
        ActionType.DUELS_WON: 30,
        ActionType.TACKLES: 110,
        ActionType.INTERCEPTIONS: 90,
        ActionType.BLOCKS: 150,
        ActionType.FOULS_DRAWN: 50,
        ActionType.PASSES_COMPLETED: 2,
        ActionType.FOULS_COMMITTED: -30,
        ActionType.YELLOW_CARD: -150,
        ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 200,
        ActionType.DRIBBLES_PAST: 0,
    },
    PositionGroup.MF: {
        ActionType.GOAL: 700,
        ActionType.GOAL_PENALTY: 380,
        ActionType.GOAL_SHOOTOUT: 380,
        ActionType.ASSIST: 520,
        ActionType.CORNER_ASSIST: 280,
        ActionType.XG_NO_GOAL: 50,
        ActionType.XA_NO_ASSIST: 100,
        ActionType.DRIBBLES_WON: 100,
        ActionType.DUELS_WON: 25,
        ActionType.TACKLES: 110,
        ActionType.INTERCEPTIONS: 150,
        ActionType.BLOCKS: 100,
        ActionType.FOULS_DRAWN: 35,
        ActionType.PASSES_COMPLETED: 3,
        ActionType.FOULS_COMMITTED: -20,
        ActionType.YELLOW_CARD: -150,
        ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 180,
        ActionType.DRIBBLES_PAST: -20,
    },
    PositionGroup.DF: {
        ActionType.GOAL: 850,
        ActionType.GOAL_PENALTY: 380,
        ActionType.GOAL_SHOOTOUT: 380,
        ActionType.ASSIST: 640,
        ActionType.CORNER_ASSIST: 320,
        ActionType.XG_NO_GOAL: 30,
        ActionType.XA_NO_ASSIST: 80,
        ActionType.DRIBBLES_WON: 130,
        ActionType.DUELS_WON: 25,
        ActionType.TACKLES: 150,
        ActionType.INTERCEPTIONS: 200,
        ActionType.BLOCKS: 130,
        ActionType.FOULS_DRAWN: 20,
        ActionType.PASSES_COMPLETED: 1,
        ActionType.FOULS_COMMITTED: -15,
        ActionType.YELLOW_CARD: -150,
        ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 80,
        ActionType.DRIBBLES_PAST: -50,
    },
}

# ---------------------------------------------------------------------------
# Base points table v2 — 5 position groups (DEL, EXT, MF, LAT, DC)
# ---------------------------------------------------------------------------

BASE_POINTS_TABLE_V2: dict[PositionGroup, dict[ActionType, int]] = {
    PositionGroup.DEL: {
        ActionType.GOAL: 650, ActionType.GOAL_PENALTY: 390, ActionType.GOAL_SHOOTOUT: 390,
        ActionType.ASSIST: 500, ActionType.CORNER_ASSIST: 250,
        ActionType.XG_NO_GOAL: 60, ActionType.XA_NO_ASSIST: 60,
        ActionType.DRIBBLES_WON: 70, ActionType.DUELS_WON: 18,
        ActionType.TACKLES: 80, ActionType.INTERCEPTIONS: 70, ActionType.BLOCKS: 100,
        ActionType.FOULS_DRAWN: 40, ActionType.PASSES_COMPLETED: 1,
        ActionType.FOULS_COMMITTED: -25, ActionType.YELLOW_CARD: -120, ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 220, ActionType.DRIBBLES_PAST: 0,
    },
    PositionGroup.EXT: {
        ActionType.GOAL: 550, ActionType.GOAL_PENALTY: 300, ActionType.GOAL_SHOOTOUT: 300,
        ActionType.ASSIST: 480, ActionType.CORNER_ASSIST: 260,
        ActionType.XG_NO_GOAL: 65, ActionType.XA_NO_ASSIST: 85,
        ActionType.DRIBBLES_WON: 110, ActionType.DUELS_WON: 18,
        ActionType.TACKLES: 75, ActionType.INTERCEPTIONS: 70, ActionType.BLOCKS: 90,
        ActionType.FOULS_DRAWN: 60, ActionType.PASSES_COMPLETED: 1,
        ActionType.FOULS_COMMITTED: -25, ActionType.YELLOW_CARD: -120, ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 220, ActionType.DRIBBLES_PAST: 0,
    },
    PositionGroup.MCO: {
        ActionType.GOAL: 600, ActionType.GOAL_PENALTY: 310, ActionType.GOAL_SHOOTOUT: 310,
        ActionType.ASSIST: 520, ActionType.CORNER_ASSIST: 260,
        ActionType.XG_NO_GOAL: 70, ActionType.XA_NO_ASSIST: 90,
        ActionType.DRIBBLES_WON: 110, ActionType.DUELS_WON: 10,
        ActionType.TACKLES: 55, ActionType.INTERCEPTIONS: 70, ActionType.BLOCKS: 90,
        ActionType.FOULS_DRAWN: 35, ActionType.PASSES_COMPLETED: 2,
        ActionType.FOULS_COMMITTED: -25, ActionType.YELLOW_CARD: -150, ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 180, ActionType.DRIBBLES_PAST: -15,
    },
    PositionGroup.MF: {
        ActionType.GOAL: 720, ActionType.GOAL_PENALTY: 350, ActionType.GOAL_SHOOTOUT: 350,
        ActionType.ASSIST: 550, ActionType.CORNER_ASSIST: 280,
        ActionType.XG_NO_GOAL: 55, ActionType.XA_NO_ASSIST: 95,
        ActionType.DRIBBLES_WON: 80, ActionType.DUELS_WON: 18,
        ActionType.TACKLES: 95, ActionType.INTERCEPTIONS: 130, ActionType.BLOCKS: 80,
        ActionType.FOULS_DRAWN: 25, ActionType.PASSES_COMPLETED: 7,
        ActionType.FOULS_COMMITTED: -20, ActionType.YELLOW_CARD: -120, ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 180, ActionType.DRIBBLES_PAST: -20,
    },
    PositionGroup.LAT: {
        ActionType.GOAL: 850, ActionType.GOAL_PENALTY: 350, ActionType.GOAL_SHOOTOUT: 350,
        ActionType.ASSIST: 620, ActionType.CORNER_ASSIST: 300,
        ActionType.XG_NO_GOAL: 45, ActionType.XA_NO_ASSIST: 90,
        ActionType.DRIBBLES_WON: 95, ActionType.DUELS_WON: 18,
        ActionType.TACKLES: 100, ActionType.INTERCEPTIONS: 120, ActionType.BLOCKS: 110,
        ActionType.FOULS_DRAWN: 25, ActionType.PASSES_COMPLETED: 1,
        ActionType.FOULS_COMMITTED: -15, ActionType.YELLOW_CARD: -120, ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 120, ActionType.DRIBBLES_PAST: -45,
    },
    PositionGroup.DC: {
        ActionType.GOAL: 1000, ActionType.GOAL_PENALTY: 350, ActionType.GOAL_SHOOTOUT: 350,
        ActionType.ASSIST: 850, ActionType.CORNER_ASSIST: 450,
        ActionType.XG_NO_GOAL: 50, ActionType.XA_NO_ASSIST: 120,
        ActionType.DRIBBLES_WON: 40, ActionType.DUELS_WON: 25,
        ActionType.TACKLES: 90, ActionType.INTERCEPTIONS: 160, ActionType.BLOCKS: 180,
        ActionType.FOULS_DRAWN: 15, ActionType.PASSES_COMPLETED: 1,
        ActionType.FOULS_COMMITTED: -15, ActionType.YELLOW_CARD: -120, ActionType.RED_CARD: -500,
        ActionType.PENALTY_WON: 80, ActionType.DRIBBLES_PAST: -60,
    },
}

_GOAL_OR_ASSIST_ACTIONS = {
    ActionType.GOAL,
    ActionType.GOAL_PENALTY,
    ActionType.ASSIST,
    ActionType.CORNER_ASSIST,
}


class SFAScoringService:
    """
    Single entry-point for all SFA scoring calculations.

    Accepts an optional ScoringConfig. When None, uses ScoringConfig.default()
    which mirrors the hardcoded BASE_POINTS_TABLE — fully backward-compatible.

    Two scoring paths:
    1. score_event() — individual actions (goals, assists) with full context:
       pts = base_pts × MIN(MAX(M1 × M2 × M3 × M4 × Mvisit, clamp_min), clamp_max)

    2. score_match_stats() — per-match aggregated stats (xG, duels, etc.):
       pts = value × base_pts × MIN(MAX(M1 × M2 × Mrating, clamp_min), clamp_max)
    """

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self._config = config if config is not None else ScoringConfig.default()

    def _resolve_group(self, group: PositionGroup) -> PositionGroup:
        """Return group if present in config, else fall back to nearest equivalent."""
        if group in self._config.base_points:
            return group
        # MCO and other fine-grained groups fall back to MF for v1 configs
        return PositionGroup.MF if PositionGroup.MF in self._config.base_points else next(iter(self._config.base_points))

    def score_event(
        self,
        group: PositionGroup,
        action: ActionType,
        player_team_pos: int,
        rival_team_pos: int,
        stage_factor: float,
        minute: int,
        score_diff: int,
        is_penalty: bool,
        psxg: float | None,
        is_away: bool,
    ) -> SFAScore:
        """Calculate the SFA score for a single event (goal or assist)."""
        base_pts = float(self._config.base_points[self._resolve_group(group)][action])
        is_goal_or_assist = action in self._config.mvisit_eligible_actions

        m1 = M1RivalDifficulty(player_team_pos, rival_team_pos)
        m2 = M2CompetitionStage(stage_factor)
        m3 = M3MinuteScore(minute, score_diff, is_penalty)
        m4 = M4ShotDifficulty(psxg if is_goal_or_assist else None)
        mvisit = MvisitFactor(is_away, is_goal_or_assist)
        combined = CombinedMultiplier(m1, m2, m3, m4, mvisit)

        return SFAScore(base_pts=base_pts, multiplier=combined)

    def score_match_stats(
        self,
        group: PositionGroup,
        stats: dict[ActionType, int | float],
        player_team_pos: int,
        rival_team_pos: int,
        stage_factor: float,
        rating: float | None = None,
    ) -> list[SFAScore]:
        """Calculate SFA scores for per-match statistics."""
        m1 = M1RivalDifficulty(player_team_pos, rival_team_pos)
        m2 = M2CompetitionStage(stage_factor)
        m3 = M3MinuteScore(minute=1, score_diff=0, is_penalty=False)  # neutral
        m4 = M4ShotDifficulty(psxg=None)  # neutral: 1.0
        mvisit = MvisitFactor(is_away=False, is_goal_or_assist=False)  # neutral: 1.0
        mrating = MratingFactor(rating)
        combined = CombinedMultiplier(m1, m2, m3, m4, mvisit, mrating)

        scores: list[SFAScore] = []
        resolved = self._resolve_group(group)
        for action, count_or_value in stats.items():
            base_per_unit = self._config.base_points[resolved][action]
            if base_per_unit == 0 or count_or_value == 0:
                continue
            base_pts = float(base_per_unit) * float(count_or_value)
            scores.append(SFAScore(base_pts=base_pts, multiplier=combined))

        return scores
