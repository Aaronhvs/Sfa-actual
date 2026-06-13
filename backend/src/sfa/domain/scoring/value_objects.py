from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sfa.infrastructure.models.enums import Position


class PositionGroup(str, Enum):
    # v2 groups (6 specific positions)
    DEL = "DEL"   # Delantero / striker
    EXT = "EXT"   # Extremo / winger
    MF  = "MF"    # Mediocampista / midfielder
    MCO = "MCO"   # Mediapunta / attacking midfielder
    LAT = "LAT"   # Lateral / full-back
    DC  = "DC"    # Defensa central / center-back
    # v1 legacy groups — kept for backward-compat with configs stored in DB
    # New configs should NOT use these.
    FW  = "FW"    # deprecated: grouped DEL+EXT
    DF  = "DF"    # deprecated: grouped DC+LAT


def position_to_group(position: Position) -> PositionGroup:
    """Map a player Position to a PositionGroup for scoring purposes.

    Uses the v2 five-group mapping. GK raises ValueError (no scoring group defined).
    """
    mapping: dict[Position, PositionGroup] = {
        Position.DEL: PositionGroup.DEL,
        Position.EXT: PositionGroup.EXT,
        Position.MC:  PositionGroup.MF,
        Position.MCO: PositionGroup.MCO,
        Position.LAT: PositionGroup.LAT,
        Position.DC:  PositionGroup.DC,
    }
    if position not in mapping:
        raise ValueError(f"No scoring group defined for position: {position!r}")
    return mapping[position]


class ActionType(str, Enum):
    GOAL             = "goal"
    GOAL_PENALTY     = "goal_penalty"
    GOAL_SHOOTOUT    = "goal_shootout"
    ASSIST           = "assist"
    CORNER_ASSIST    = "corner_assist"
    XG_NO_GOAL       = "xg_no_goal"
    XA_NO_ASSIST     = "xa_no_assist"
    DRIBBLES_WON     = "dribbles_won"
    DUELS_WON        = "duels_won"
    TACKLES          = "tackles"
    INTERCEPTIONS    = "interceptions"
    BLOCKS           = "blocks"
    FOULS_DRAWN      = "fouls_drawn"
    PASSES_COMPLETED = "passes_completed"
    FOULS_COMMITTED  = "fouls_committed"
    YELLOW_CARD      = "yellow_card"
    RED_CARD         = "red_card"
    PENALTY_WON      = "penalty_won"
    DRIBBLES_PAST    = "dribbles_past"


# ---------------------------------------------------------------------------
# DiminishingReturnsConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DiminishingReturnsConfig:
    """Controls diminishing returns for accumulative actions.

    The first `cap` occurrences score at 100% of base_pts.
    Any occurrences beyond `cap` score at `extra_factor` × base_pts.
    """

    cap: int
    extra_factor: float

    def __post_init__(self) -> None:
        if self.cap <= 0:
            raise ValueError(f"cap must be > 0, got {self.cap}")
        if not (0.0 < self.extra_factor < 1.0):
            raise ValueError(
                f"extra_factor must be in (0, 1), got {self.extra_factor}"
            )

    @staticmethod
    def apply(n: float, base_pts_per_unit: float, cfg: DiminishingReturnsConfig) -> float:
        """Calculate total points for `n` occurrences with diminishing returns."""
        full_count = min(n, cfg.cap)
        extra_count = max(0.0, n - cfg.cap)
        return full_count * base_pts_per_unit + extra_count * base_pts_per_unit * cfg.extra_factor


# ---------------------------------------------------------------------------
# TeamStrengthBlend
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TeamStrengthBlend:
    """Blended team strength (0–100) from previous and current season standings.

    Blend weights by matchday:
      1-5:   80% prev + 20% curr
      6-10:  60% prev + 40% curr
      11-15: 40% prev + 60% curr
      16+:   20% prev + 80% curr
      None:  50% / 50%
    """

    value: float

    def __init__(
        self,
        prev_season_strength: float | None,
        current_season_strength: float | None,
        matchday: int | None = None,
        fallback_strength: float = 30.0,
    ) -> None:
        if prev_season_strength is None and current_season_strength is None:
            blended = fallback_strength
        elif prev_season_strength is None:
            blended = float(current_season_strength)  # type: ignore[arg-type]
        elif current_season_strength is None:
            blended = float(prev_season_strength)
        else:
            if matchday is None:
                w_prev, w_curr = 0.5, 0.5
            elif matchday <= 5:
                w_prev, w_curr = 0.8, 0.2
            elif matchday <= 10:
                w_prev, w_curr = 0.6, 0.4
            elif matchday <= 15:
                w_prev, w_curr = 0.4, 0.6
            else:
                w_prev, w_curr = 0.2, 0.8
            blended = w_prev * prev_season_strength + w_curr * current_season_strength

        object.__setattr__(self, "value", max(0.0, min(100.0, blended)))


# ---------------------------------------------------------------------------
# M1 – M4, Mvisit, Mrating, CombinedMultiplier, SFAScore
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class M1RivalDifficulty:
    """Rival difficulty multiplier.

    v2 mode (both strengths provided):
        M1 = 1.0 + (rival_strength - player_strength) / m1_strength_divisor
        Clamped to config.m1_clamp (default [0.6, 1.8]).

    Legacy fallback (strengths not provided):
        M1 = 1.0 + (player_team_pos - rival_team_pos) / m1_divisor
        Clamped to [0.5, 2.0].

    If no data at all: M1 = 1.0 (neutral).
    """

    value: float

    def __init__(
        self,
        player_team_pos: int | None = None,
        rival_team_pos: int | None = None,
        player_team_strength: float | None = None,
        rival_team_strength: float | None = None,
        config: ScoringConfig | None = None,
    ) -> None:
        clamp_min, clamp_max = config.m1_clamp if config else (0.5, 2.0)
        strength_divisor = config.m1_strength_divisor if config else 100.0
        pos_divisor = config.m1_divisor if config else 20.0

        if player_team_strength is not None and rival_team_strength is not None:
            raw = 1.0 + (rival_team_strength - player_team_strength) / strength_divisor
        elif player_team_pos is not None and rival_team_pos is not None:
            # legacy formula — use legacy clamp bounds when no config
            raw = 1.0 + (player_team_pos - rival_team_pos) / pos_divisor
            if config is None:
                clamp_min, clamp_max = 0.5, 2.0
        else:
            raw = 1.0

        object.__setattr__(self, "value", max(clamp_min, min(clamp_max, raw)))


@dataclass(frozen=True)
class M2CompetitionStage:
    """Wraps the stage_factor stored in CompetitionStage.stage_factor."""

    value: float

    def __init__(self, stage_factor: float) -> None:
        if stage_factor <= 0:
            raise ValueError(f"stage_factor must be > 0, got {stage_factor}")
        object.__setattr__(self, "value", float(stage_factor))


@dataclass(frozen=True)
class M3MinuteScore:
    """Context multiplier based on match minute and score differential.

    score_diff = player_team_goals − rival_goals at moment of action.
    Negative → losing · Zero → drawing · Positive → winning
    """

    value: float

    def __init__(
        self,
        minute: int,
        score_diff: int,
        is_penalty: bool,
        is_shootout: bool = False,
    ) -> None:
        if is_shootout:
            v = 1.5
        elif is_penalty:
            v = 0.6
        elif 80 <= minute <= 90:
            if score_diff <= 0:
                v = 2.5
            elif score_diff == 1:
                v = 1.4
            else:
                v = 0.7
        elif 70 <= minute <= 79:
            if score_diff == 0:
                v = 1.8
            elif score_diff < 0:
                v = 1.6
            else:
                v = 1.0
        elif 45 <= minute <= 69:
            if score_diff < 0:
                v = 1.3
            elif score_diff == 0:
                v = 1.2
            else:
                v = 1.0
        elif 1 <= minute <= 44:
            v = 1.0
        else:
            raise ValueError(f"minute must be in [1, 90], got {minute}")
        object.__setattr__(self, "value", v)


@dataclass(frozen=True)
class M4ShotDifficulty:
    """Shot difficulty based on post-shot expected goals.

    v2: default PSxG uses M4=1.0 (no bonus for missing data).
    M4 clamped to config.m4_clamp (default [1.0, 1.5] in v2, [1.0, 1.8] in v1).
    """

    value: float

    def __init__(
        self,
        psxg: float | None = None,
        config: ScoringConfig | None = None,
    ) -> None:
        clamp_min = 1.0
        clamp_max = config.m4_clamp[1] if config else 1.8
        multiplier = config.m4_psxg_multiplier if config else 0.8

        if psxg is None:
            v = 1.0
        else:
            raw = 1.0 + (1.0 - psxg) * multiplier
            v = max(clamp_min, min(clamp_max, raw))
        object.__setattr__(self, "value", v)


@dataclass(frozen=True)
class MvisitFactor:
    """Away bonus for goals and assists.

    v2 default: 1.15 (down from 1.3 in v1).
    Reads bonus from config if provided.
    """

    value: float

    def __init__(
        self,
        is_away: bool,
        is_goal_or_assist: bool,
        config: ScoringConfig | None = None,
    ) -> None:
        bonus = config.mvisit_bonus if config else 1.3
        v = float(bonus) if (is_away and is_goal_or_assist) else 1.0
        object.__setattr__(self, "value", v)


@dataclass(frozen=True)
class MratingFactor:
    """Rating-based scale applied to stats events.

    v1 thresholds: None→0.5, <7.0→0.3, [7.0,8.0)→0.5, [8.0,8.5)→0.75, ≥8.5→1.0
    v2 thresholds: None→0.75, <6.5→0.50, [6.5,7.0)→0.70, [7.0,7.5)→0.85,
                   [7.5,8.0)→1.00, [8.0,8.5)→1.15, ≥8.5→1.30
    """

    value: float

    def __init__(self, rating: float | None, config: ScoringConfig | None = None) -> None:
        if config is not None:
            if rating is None:
                v = config.mrating_none_value
            else:
                v = config.mrating_top_value
                for threshold, factor in sorted(config.mrating_thresholds, key=lambda t: t[0]):
                    if rating < threshold:
                        v = factor
                        break
        else:
            # v1 legacy behavior
            if rating is None:
                v = 0.5
            elif rating < 7.0:
                v = 0.3
            elif rating < 8.0:
                v = 0.5
            elif rating < 8.5:
                v = 0.75
            else:
                v = 1.0
        object.__setattr__(self, "value", v)


@dataclass(frozen=True)
class CombinedMultiplier:
    """Product of all context multipliers, clamped to config.combined_clamp (default [0.3, 4.0])."""

    value: float

    def __init__(
        self,
        m1: M1RivalDifficulty,
        m2: M2CompetitionStage,
        m3: M3MinuteScore,
        m4: M4ShotDifficulty,
        mvisit: MvisitFactor,
        mrating: MratingFactor | None = None,
        config: ScoringConfig | None = None,
    ) -> None:
        clamp_min, clamp_max = config.combined_clamp if config else (0.3, 4.0)
        raw = m1.value * m2.value * m3.value * m4.value * mvisit.value
        if mrating is not None:
            raw *= mrating.value
        object.__setattr__(self, "value", max(clamp_min, min(clamp_max, raw)))


@dataclass(frozen=True)
class SFAScore:
    """Final score for a single action."""

    base_pts: float
    multiplier: CombinedMultiplier
    total: float

    def __init__(self, base_pts: float, multiplier: CombinedMultiplier) -> None:
        object.__setattr__(self, "base_pts", base_pts)
        object.__setattr__(self, "multiplier", multiplier)
        object.__setattr__(self, "total", base_pts * multiplier.value)


# ---------------------------------------------------------------------------
# ScoringConfig — versionable configuration for the scoring system
# ---------------------------------------------------------------------------

_DEFAULT_MRATING_THRESHOLDS_V1: list[tuple[float, float]] = [
    (7.0, 0.3),
    (8.0, 0.5),
    (8.5, 0.75),
]
_DEFAULT_MRATING_THRESHOLDS_V2: list[tuple[float, float]] = [
    (6.5, 0.50),
    (7.0, 0.70),
    (7.5, 0.85),
    (8.0, 1.00),
    (8.5, 1.15),
]

_DEFAULT_DIMINISHING_RETURNS_V2: dict[str, dict[str, float]] = {
    "xg_no_goal":    {"cap": 3, "extra_factor": 0.30},
    "xa_no_assist":  {"cap": 4, "extra_factor": 0.30},
    "duels_won":     {"cap": 8, "extra_factor": 0.25},
    "tackles":       {"cap": 5, "extra_factor": 0.25},
    "interceptions": {"cap": 5, "extra_factor": 0.25},
    "blocks":        {"cap": 4, "extra_factor": 0.25},
}

_DEFAULT_PASSES_AVG_V2: dict[str, int] = {
    "DEL": 20, "EXT": 28, "MF": 42, "MCO": 45, "LAT": 38, "DC": 32,
}

_DEFAULT_LEAGUE_STRENGTH_FACTORS: dict[str, float] = {
    "Premier League": 1.00,
    "La Liga": 0.95,
    "Serie A": 0.90,
    "Bundesliga": 0.90,
    "Ligue 1": 0.82,
    "Primeira Liga": 0.75,
    "Eredivisie": 0.75,
    "Jupiler Pro League": 0.65,
    "Süper Lig": 0.65,
    "Scottish Premiership": 0.65,
    "default": 0.50,
}

_DEFAULT_COMPETITION_BONUS_WEIGHTS: dict[str, float] = {
    "Champions League": 1.00,
    "Europa League": 0.75,
    "Conference League": 0.55,
    "UEFA Super Cup": 0.45,
    "Premier League": 0.95,
    "La Liga": 0.90,
    "Serie A": 0.85,
    "Bundesliga": 0.85,
    "Ligue 1": 0.80,
    "FA Cup": 0.65,
    "Copa del Rey": 0.65,
    "DFB-Pokal": 0.60,
    "Coppa Italia": 0.60,
    "Coupe de France": 0.55,
    "EFL Cup": 0.45,
    "Community Shield": 0.25,
    "Supercopa de España": 0.40,
    "Supercoppa Italiana": 0.35,
    "DFL-Supercup": 0.35,
    "Trophée des Champions": 0.30,
}

_DEFAULT_ACHIEVEMENT_PHASE_BONUSES: dict[str, dict[str, int]] = {
    "champions_league": {
        "qualify_ko": 1000, "round_of_16": 1500, "quarter_final": 2200,
        "semi_final": 3000, "winner": 5000,
    },
    "europa_league": {
        "qualify_ko": 700, "round_of_16": 1000, "quarter_final": 1500,
        "semi_final": 2000, "winner": 3500,
    },
    "conference_league": {
        "qualify_ko": 500, "round_of_16": 700, "quarter_final": 1000,
        "semi_final": 1400, "winner": 2500,
    },
    "domestic_league": {
        "champion": 7000, "runner_up": 2500, "top_4": 1000,
    },
    "domestic_cup_major": {
        "semi_final": 800, "runner_up": 1200, "winner": 3000,
    },
    "domestic_cup_minor": {
        "runner_up": 300, "winner": 1000,
    },
}

_DEFAULT_CUP_LOWER_DIV_STRENGTHS: dict[str, float] = {
    "second_division": 35.0,
    "third_division": 18.0,
    "amateur": 10.0,
}


@dataclass(frozen=True)
class ScoringConfig:
    """Immutable configuration for one version of the scoring rules.

    Required fields are those present since v1. Optional v2 fields have
    sensible defaults so that old configs loaded from DB continue to work.
    """

    # ── Required fields (present in all versions) ──────────────────────────
    base_points: dict[PositionGroup, dict[ActionType, int]]
    m1_clamp: tuple[float, float]
    m1_divisor: float
    m4_psxg_multiplier: float
    m4_clamp: tuple[float, float]
    mvisit_bonus: float
    mvisit_eligible_actions: frozenset[ActionType]
    mrating_thresholds: tuple[tuple[float, float], ...]
    mrating_top_value: float
    mrating_none_value: float
    combined_clamp: tuple[float, float]

    # ── Optional v2 fields (default = backward-compatible behavior) ─────────
    diminishing_returns: dict[ActionType, DiminishingReturnsConfig] = field(
        default_factory=dict
    )
    passes_avg_by_position: dict[PositionGroup, int] = field(default_factory=dict)
    minutes_threshold_stats: int = 0
    minutes_penalty_factor: float = 1.0
    ranking_min_minutes_global: int = 90
    ranking_min_minutes_competition: int = 90
    m1_strength_divisor: float = 100.0
    league_strength_factors: dict[str, float] = field(default_factory=dict)
    promoted_champion_strength: float = 35.0
    promoted_runner_up_strength: float = 30.0
    promoted_playoff_strength: float = 25.0
    promoted_default_strength: float = 30.0
    cup_lower_div_strengths: dict[str, float] = field(default_factory=dict)
    achievement_phase_bonuses: dict[str, dict[str, int]] = field(default_factory=dict)
    competition_bonus_weights: dict[str, float] = field(default_factory=dict)
    enable_midfield_control_bonuses: bool = False
    midfield_control_bonus_cap_per_match: int = 180
    enable_performance_based_achievement_bonus: bool = False
    m1_stats_weight: float = 1.0
    m1_stats_clamp: tuple[float, float] = (0.85, 1.20)
    stats_m2_attenuation: float = 1.0

    def __post_init__(self) -> None:
        # Core clamp invariants
        for name, clamp in [("m1_clamp", self.m1_clamp), ("m4_clamp", self.m4_clamp),
                             ("combined_clamp", self.combined_clamp)]:
            if clamp[0] >= clamp[1]:
                raise ValueError(f"{name} min must be < max, got {clamp}")
            if clamp[0] <= 0 or clamp[1] <= 0:
                raise ValueError(f"{name} values must be positive, got {clamp}")
        if self.m1_divisor <= 0:
            raise ValueError(f"m1_divisor must be > 0, got {self.m1_divisor}")
        if self.m1_strength_divisor <= 0:
            raise ValueError(f"m1_strength_divisor must be > 0, got {self.m1_strength_divisor}")
        if self.mvisit_bonus < 1.0:
            raise ValueError(f"mvisit_bonus must be >= 1.0, got {self.mvisit_bonus}")
        if not self.base_points:
            raise ValueError("base_points cannot be empty")
        thresholds = self.mrating_thresholds
        for i in range(1, len(thresholds)):
            if thresholds[i][0] <= thresholds[i - 1][0]:
                raise ValueError(
                    f"mrating_thresholds must be strictly increasing, "
                    f"got {thresholds[i-1][0]} then {thresholds[i][0]}"
                )
        if not (0.0 < self.minutes_penalty_factor <= 1.0):
            raise ValueError(
                f"minutes_penalty_factor must be in (0, 1], got {self.minutes_penalty_factor}"
            )
        if self.minutes_threshold_stats < 0:
            raise ValueError(
                f"minutes_threshold_stats must be >= 0, got {self.minutes_threshold_stats}"
            )
        if not (0.0 <= self.m1_stats_weight <= 1.0):
            raise ValueError(f"m1_stats_weight must be in [0, 1], got {self.m1_stats_weight}")
        if self.m1_stats_clamp[0] >= self.m1_stats_clamp[1]:
            raise ValueError(f"m1_stats_clamp min must be < max, got {self.m1_stats_clamp}")
        if self.m1_stats_clamp[0] <= 0:
            raise ValueError(f"m1_stats_clamp values must be positive, got {self.m1_stats_clamp}")
        if not (0.0 < self.stats_m2_attenuation <= 1.0):
            raise ValueError(
                f"stats_m2_attenuation must be in (0, 1], got {self.stats_m2_attenuation}"
            )

    @classmethod
    def default(cls) -> ScoringConfig:
        """Build ScoringConfig from v1 hardcoded values (backward-compat factory)."""
        from sfa.domain.scoring.services import BASE_POINTS_TABLE  # lazy to avoid circular
        return cls(
            base_points={g: dict(v) for g, v in BASE_POINTS_TABLE.items()},
            m1_clamp=(0.5, 2.0),
            m1_divisor=20.0,
            m4_psxg_multiplier=0.8,
            m4_clamp=(1.0, 1.8),
            mvisit_bonus=1.3,
            mvisit_eligible_actions=frozenset({
                ActionType.GOAL, ActionType.GOAL_PENALTY, ActionType.GOAL_SHOOTOUT,
                ActionType.ASSIST, ActionType.CORNER_ASSIST,
            }),
            mrating_thresholds=tuple(_DEFAULT_MRATING_THRESHOLDS_V1),
            mrating_top_value=1.0,
            mrating_none_value=0.5,
            combined_clamp=(0.3, 4.0),
        )

    @classmethod
    def default_v2(cls) -> ScoringConfig:
        """Build ScoringConfig with all v2 Impact Model parameters."""
        from sfa.domain.scoring.services import BASE_POINTS_TABLE_V2  # lazy to avoid circular
        dr = {
            ActionType(k): DiminishingReturnsConfig(
                cap=int(v["cap"]), extra_factor=float(v["extra_factor"])
            )
            for k, v in _DEFAULT_DIMINISHING_RETURNS_V2.items()
        }
        passes_avg = {PositionGroup(k): v for k, v in _DEFAULT_PASSES_AVG_V2.items()}
        return cls(
            base_points={g: dict(v) for g, v in BASE_POINTS_TABLE_V2.items()},
            m1_clamp=(0.6, 1.8),
            m1_divisor=20.0,
            m4_psxg_multiplier=0.8,
            m4_clamp=(1.0, 1.5),
            mvisit_bonus=1.15,
            mvisit_eligible_actions=frozenset({
                ActionType.GOAL, ActionType.GOAL_PENALTY, ActionType.GOAL_SHOOTOUT,
                ActionType.ASSIST, ActionType.CORNER_ASSIST,
            }),
            mrating_thresholds=tuple(_DEFAULT_MRATING_THRESHOLDS_V2),
            mrating_top_value=1.30,
            mrating_none_value=0.75,
            combined_clamp=(0.3, 4.0),
            diminishing_returns=dr,
            passes_avg_by_position=passes_avg,
            minutes_threshold_stats=15,
            minutes_penalty_factor=0.50,
            ranking_min_minutes_global=600,
            ranking_min_minutes_competition=180,
            m1_strength_divisor=100.0,
            league_strength_factors=dict(_DEFAULT_LEAGUE_STRENGTH_FACTORS),
            promoted_champion_strength=35.0,
            promoted_runner_up_strength=30.0,
            promoted_playoff_strength=25.0,
            promoted_default_strength=30.0,
            cup_lower_div_strengths=dict(_DEFAULT_CUP_LOWER_DIV_STRENGTHS),
            achievement_phase_bonuses={k: dict(v) for k, v in _DEFAULT_ACHIEVEMENT_PHASE_BONUSES.items()},
            competition_bonus_weights=dict(_DEFAULT_COMPETITION_BONUS_WEIGHTS),
            enable_midfield_control_bonuses=True,
            midfield_control_bonus_cap_per_match=180,
            enable_performance_based_achievement_bonus=True,
            m1_stats_weight=0.35,
            m1_stats_clamp=(0.85, 1.20),
            stats_m2_attenuation=0.5,
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScoringConfig:
        """Deserialize from a config_json dict. Accepts both v1 and v2 formats."""
        try:
            raw_bp = d["base_points"]
            base_points: dict[PositionGroup, dict[ActionType, int]] = {}
            for group_str, actions in raw_bp.items():
                group = PositionGroup(group_str)
                base_points[group] = {ActionType(k): int(v) for k, v in actions.items()}

            m1_clamp = tuple(d["m1_clamp"])
            m4_clamp = tuple(d["m4_clamp"])
            combined_clamp = tuple(d["combined_clamp"])
            mrating_thresholds = tuple(
                (float(t[0]), float(t[1])) for t in d["mrating_thresholds"]
            )
            mvisit_eligible = frozenset(ActionType(a) for a in d["mvisit_eligible_actions"])

            # v2 optional fields — defaults for backward compat with v1 configs
            dr: dict[ActionType, DiminishingReturnsConfig] = {}
            for k, v in d.get("diminishing_returns", {}).items():
                dr[ActionType(k)] = DiminishingReturnsConfig(
                    cap=int(v["cap"]), extra_factor=float(v["extra_factor"])
                )

            passes_avg: dict[PositionGroup, int] = {
                PositionGroup(k): int(v)
                for k, v in d.get("passes_avg_by_position", {}).items()
            }

            achievement_bonuses: dict[str, dict[str, int]] = {
                k: {p: int(pts) for p, pts in v.items()}
                for k, v in d.get("achievement_phase_bonuses", {}).items()
            }

            return cls(
                base_points=base_points,
                m1_clamp=(float(m1_clamp[0]), float(m1_clamp[1])),
                m1_divisor=float(d["m1_divisor"]),
                m4_psxg_multiplier=float(d["m4_psxg_multiplier"]),
                m4_clamp=(float(m4_clamp[0]), float(m4_clamp[1])),
                mvisit_bonus=float(d["mvisit_bonus"]),
                mvisit_eligible_actions=mvisit_eligible,
                mrating_thresholds=mrating_thresholds,
                mrating_top_value=float(d["mrating_top_value"]),
                mrating_none_value=float(d["mrating_none_value"]),
                combined_clamp=(float(combined_clamp[0]), float(combined_clamp[1])),
                diminishing_returns=dr,
                passes_avg_by_position=passes_avg,
                minutes_threshold_stats=int(d.get("minutes_threshold_stats", 0)),
                minutes_penalty_factor=float(d.get("minutes_penalty_factor", 1.0)),
                ranking_min_minutes_global=int(d.get("ranking_min_minutes_global", 90)),
                ranking_min_minutes_competition=int(d.get("ranking_min_minutes_competition", 90)),
                m1_strength_divisor=float(d.get("m1_strength_divisor", 100.0)),
                league_strength_factors=dict(d.get("league_strength_factors", {})),
                promoted_champion_strength=float(d.get("promoted_champion_strength", 35.0)),
                promoted_runner_up_strength=float(d.get("promoted_runner_up_strength", 30.0)),
                promoted_playoff_strength=float(d.get("promoted_playoff_strength", 25.0)),
                promoted_default_strength=float(d.get("promoted_default_strength", 30.0)),
                cup_lower_div_strengths={
                    k: float(v) for k, v in d.get("cup_lower_div_strengths", {}).items()
                },
                achievement_phase_bonuses=achievement_bonuses,
                competition_bonus_weights=dict(d.get("competition_bonus_weights", {})),
                enable_midfield_control_bonuses=bool(d.get("enable_midfield_control_bonuses", False)),
                midfield_control_bonus_cap_per_match=int(d.get("midfield_control_bonus_cap_per_match", 180)),
                enable_performance_based_achievement_bonus=bool(
                    d.get("enable_performance_based_achievement_bonus", False)
                ),
                m1_stats_weight=float(d.get("m1_stats_weight", 1.0)),
                m1_stats_clamp=tuple(d.get("m1_stats_clamp", [0.85, 1.20])),
                stats_m2_attenuation=float(d.get("stats_m2_attenuation", 1.0)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid ScoringConfig dict: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict suitable for storage as config_json JSONB."""
        return {
            "base_points": {
                g.value: {a.value: v for a, v in actions.items()}
                for g, actions in self.base_points.items()
            },
            "m1_clamp": list(self.m1_clamp),
            "m1_divisor": self.m1_divisor,
            "m4_psxg_multiplier": self.m4_psxg_multiplier,
            "m4_clamp": list(self.m4_clamp),
            "mvisit_bonus": self.mvisit_bonus,
            "mvisit_eligible_actions": [a.value for a in self.mvisit_eligible_actions],
            "mrating_thresholds": [list(t) for t in self.mrating_thresholds],
            "mrating_top_value": self.mrating_top_value,
            "mrating_none_value": self.mrating_none_value,
            "combined_clamp": list(self.combined_clamp),
            "diminishing_returns": {
                a.value: {"cap": cfg.cap, "extra_factor": cfg.extra_factor}
                for a, cfg in self.diminishing_returns.items()
            },
            "passes_avg_by_position": {g.value: v for g, v in self.passes_avg_by_position.items()},
            "minutes_threshold_stats": self.minutes_threshold_stats,
            "minutes_penalty_factor": self.minutes_penalty_factor,
            "ranking_min_minutes_global": self.ranking_min_minutes_global,
            "ranking_min_minutes_competition": self.ranking_min_minutes_competition,
            "m1_strength_divisor": self.m1_strength_divisor,
            "league_strength_factors": dict(self.league_strength_factors),
            "promoted_champion_strength": self.promoted_champion_strength,
            "promoted_runner_up_strength": self.promoted_runner_up_strength,
            "promoted_playoff_strength": self.promoted_playoff_strength,
            "promoted_default_strength": self.promoted_default_strength,
            "cup_lower_div_strengths": dict(self.cup_lower_div_strengths),
            "achievement_phase_bonuses": {
                k: dict(v) for k, v in self.achievement_phase_bonuses.items()
            },
            "competition_bonus_weights": dict(self.competition_bonus_weights),
            "enable_midfield_control_bonuses": self.enable_midfield_control_bonuses,
            "midfield_control_bonus_cap_per_match": self.midfield_control_bonus_cap_per_match,
            "enable_performance_based_achievement_bonus": self.enable_performance_based_achievement_bonus,
            "m1_stats_weight": self.m1_stats_weight,
            "m1_stats_clamp": list(self.m1_stats_clamp),
            "stats_m2_attenuation": self.stats_m2_attenuation,
        }
