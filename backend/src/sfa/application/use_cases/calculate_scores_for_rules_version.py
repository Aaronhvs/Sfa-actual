from __future__ import annotations

from dataclasses import dataclass
import logging

from sfa.domain.scoring.entities import PlayerEventScore
from sfa.domain.scoring.services import SFAScoringService
from sfa.domain.scoring.value_objects import (
    ActionType,
    M1RivalDifficulty,
    M2CompetitionStage,
    M3MinuteScore,
    M4ShotDifficulty,
    MratingFactor,
    MvisitFactor,
    PositionGroup,
    ScoringConfig,
    position_to_group,
)
from sfa.domain.scoring_ports import (
    PlayerEventRawContextDTO,
    PlayerEventScoreRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)
from sfa.infrastructure.models.enums import EventType, Position

logger = logging.getLogger(__name__)

MIN_MINUTES_FOR_RANKING = 90

_STATS_EVENT_TYPE = EventType.STATS.value

# ── Midfield control bonus constants ────────────────────────────────────────
# Stats actions that receive full M1 (decisive); all others receive damped M1_stats
_M1_DECISIVE_STATS_ACTIONS: frozenset = frozenset({ActionType.PENALTY_WON})

_MC_BONUS_MIN_MINUTES = 60

_MC_BONUS_CONTROL = 140      # CONTROL_MIDFIELD_BONUS base pts
_MC_BONUS_TWO_WAY = 90       # TWO_WAY_MIDFIELD_BONUS base pts
_MC_BONUS_CREATIVE = 70      # CREATIVE_CONTROL_BONUS base pts

_MC_CONTROL_MIN_RATING = 7.6
_MC_CONTROL_MIN_PASSES = 65
_MC_CONTROL_MIN_ACCURACY = 90.0

_MC_TWO_WAY_MIN_RATING = 7.4
_MC_TWO_WAY_MIN_PASSES = 50
_MC_TWO_WAY_MIN_DEFENSIVE = 3   # tackles_won + interceptions

_MC_CREATIVE_MIN_RATING = 7.7
_MC_CREATIVE_MIN_PASSES = 55
_MC_CREATIVE_MIN_PASSES_ACCURACY = 85.0
_MC_CREATIVE_MIN_PASSES_KEY = 2


@dataclass(frozen=True)
class CalculateScoresForRulesVersionResult:
    rules_version_id: int
    season: str
    competition_id: int | None
    events_calculated: int
    players_updated: int
    status: str
    error: str | None


class CalculateScoresForRulesVersionUseCase:
    def __init__(
        self,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
        event_score_repo: PlayerEventScoreRepositoryPort,
    ) -> None:
        self._rules_version_repo = rules_version_repo
        self._event_score_repo = event_score_repo

    async def execute(
        self,
        rules_version_id: int,
        season: str,
        competition_id: int | None = None,
        match_id: int | None = None,
        player_id: int | None = None,
        force_recalculate: bool = False,
    ) -> CalculateScoresForRulesVersionResult:
        rules_version = await self._rules_version_repo.get_version_by_id(rules_version_id)
        if rules_version is None:
            return CalculateScoresForRulesVersionResult(
                rules_version_id=rules_version_id, season=season,
                competition_id=competition_id, events_calculated=0, players_updated=0,
                status="failed", error=f"ScoringRulesVersion id={rules_version_id} not found",
            )

        service = SFAScoringService(config=rules_version.config)
        events = await self._event_score_repo.get_events_for_recalc(
            season=season,
            competition_id=competition_id,
            match_id=match_id,
            player_id=player_id,
        )

        # Preload competition name map for midfield bonus competition_weight lookup
        competition_name_map: dict[int, str] = {}
        if rules_version.config.enable_midfield_control_bonuses:
            competition_name_map = await self._event_score_repo.get_competition_name_map()

        events_calculated = 0

        for event in events:
            if not force_recalculate:
                if await self._event_score_repo.event_score_exists(event.event_id, rules_version_id):
                    continue

            score = self._score_event(event, service, rules_version_id, competition_name_map)
            if score is None:
                continue

            await self._event_score_repo.upsert_event_score(score)
            events_calculated += 1

        players_updated = await self._event_score_repo.bulk_rebuild_season_scores(
            rules_version_id=rules_version_id,
            season=season,
            competition_id=competition_id,
        )

        logger.info(
            "[CalculateScoresForRulesVersionUseCase] rules_version_id=%d season=%s "
            "competition_id=%s events_calculated=%d players_updated=%d",
            rules_version_id, season, competition_id, events_calculated, players_updated,
        )
        return CalculateScoresForRulesVersionResult(
            rules_version_id=rules_version_id,
            season=season,
            competition_id=competition_id,
            events_calculated=events_calculated,
            players_updated=players_updated,
            status="completed",
            error=None,
        )

    def _score_event(
        self,
        event: PlayerEventRawContextDTO,
        service: SFAScoringService,
        rules_version_id: int,
        competition_name_map: dict[int, str] | None = None,
    ) -> PlayerEventScore | None:
        """Score a single raw event using the given SFAScoringService.

        Returns None if the event can't be scored (unknown position or action).
        """
        try:
            position = Position(event.player_position)
            group = position_to_group(position)
        except (ValueError, TypeError):
            logger.warning(
                "[CalculateScoresForRulesVersionUseCase] Skipping event_id=%d: "
                "unknown position %r", event.event_id, event.player_position,
            )
            return None

        is_stats = event.event_type == _STATS_EVENT_TYPE

        if is_stats:
            return self._score_stats_event(
                event, service, group, position, rules_version_id,
                competition_name_map or {},
            )
        else:
            return self._score_individual_event(event, service, group, position, rules_version_id)

    def _score_individual_event(
        self, event, service, group, position, rules_version_id,
    ) -> PlayerEventScore | None:
        try:
            action = ActionType(event.event_type)
        except ValueError:
            logger.warning(
                "[CalculateScoresForRulesVersionUseCase] Skipping event_id=%d: "
                "unknown action %r", event.event_id, event.event_type,
            )
            return None

        config = service._config
        player_team_pos = event.player_team_pos or 10
        rival_team_pos = event.rival_team_pos or 10
        is_away = event.is_away or False
        minute = max(1, min(90, event.minute))
        score_diff = event.score_diff if event.score_diff is not None else 0
        is_penalty = action == ActionType.GOAL_PENALTY
        is_shootout = action == ActionType.GOAL_SHOOTOUT

        # v2: use team strength when available, fall back to position
        m1 = M1RivalDifficulty(
            player_team_pos=player_team_pos,
            rival_team_pos=rival_team_pos,
            player_team_strength=getattr(event, "player_team_strength", None),
            rival_team_strength=getattr(event, "rival_team_strength", None),
            config=config,
        )
        m2 = M2CompetitionStage(event.stage_factor)
        m3 = M3MinuteScore(minute, score_diff, is_penalty, is_shootout=is_shootout)
        is_eligible = action in config.mvisit_eligible_actions
        m4 = M4ShotDifficulty(event.psxg if is_eligible else None, config=config)
        mvisit = MvisitFactor(is_away, is_eligible, config=config)
        mrating_val = 1.0

        raw = m1.value * m2.value * m3.value * m4.value * mvisit.value
        combined = max(config.combined_clamp[0], min(config.combined_clamp[1], raw))
        try:
            base = float(config.base_points[group][action])
        except KeyError:
            logger.warning(
                "[CalculateScoresForRulesVersionUseCase] No base_points entry for group=%r action=%r "
                "rules_version_id=%d — skipping event_id=%d",
                group, action, rules_version_id, event.event_id,
            )
            return None
        final = round(base * combined, 2)

        strength_used = (
            getattr(event, "player_team_strength", None) is not None
            and getattr(event, "rival_team_strength", None) is not None
        )
        details = {
            "action": action.value,
            "position": position.value,
            "base": base,
            "M1": round(m1.value, 3),
            "M2": round(m2.value, 3),
            "M3": round(m3.value, 3),
            "M4": round(m4.value, 3),
            "Mvisit": round(mvisit.value, 2),
            "Mrating": mrating_val,
            "combined_before_clamp": round(raw, 4),
            "combined_after_clamp": round(combined, 4),
            "final_points": final,
            "strength_used": strength_used,
        }

        return PlayerEventScore(
            id=None, event_id=event.event_id, player_id=event.player_id,
            fixture_id=event.fixture_id, season=event.season,
            competition_id=event.competition_id, rules_version_id=rules_version_id,
            action_type=action.value, position=position.value,
            base_points=base, m1=round(m1.value, 3), m2=round(m2.value, 3),
            m3=round(m3.value, 3), m4=round(m4.value, 3),
            mvisit=round(mvisit.value, 2), mrating=mrating_val,
            combined_before_clamp=round(raw, 4), combined_after_clamp=round(combined, 4),
            final_points=final, calculation_details=details, created_at=None,
        )

    def _score_stats_event(
        self, event, service, group, position, rules_version_id,
        competition_name_map: dict | None = None,
    ) -> PlayerEventScore | None:
        from sfa.domain.scoring.value_objects import DiminishingReturnsConfig, PositionGroup

        config = service._config
        player_team_pos = event.player_team_pos or 10
        rival_team_pos = event.rival_team_pos or 10

        # v2: use team strength when available
        m1 = M1RivalDifficulty(
            player_team_pos=player_team_pos,
            rival_team_pos=rival_team_pos,
            player_team_strength=getattr(event, "player_team_strength", None),
            rival_team_strength=getattr(event, "rival_team_strength", None),
            config=config,
        )
        attenuation = config.stats_m2_attenuation
        effective_sf = 1.0 + (event.stage_factor - 1.0) * attenuation
        m2 = M2CompetitionStage(effective_sf)
        mrating = MratingFactor(event.rating, config=config)

        m1_original = m1.value
        weight = config.m1_stats_weight
        clamp_min, clamp_max = config.m1_stats_clamp
        m1_stats_applied = max(clamp_min, min(clamp_max, 1.0 + (m1_original - 1.0) * weight))

        raw = m1_original * m2.value * mrating.value
        combined = max(config.combined_clamp[0], min(config.combined_clamp[1], raw))

        # v2: minutes threshold — penalize stats for very short appearances
        minutes = getattr(event, "minutes", None) or 0
        threshold = config.minutes_threshold_stats  # 0 = disabled (v1 backward compat)
        minutes_penalty_applied = threshold > 0 and minutes < threshold
        minutes_scale = config.minutes_penalty_factor if minutes_penalty_applied else 1.0

        g = event.goals or 0
        a = event.assists or 0
        # passes_accuracy from API-Football stores completed passes COUNT, not percentage
        passes_completed_raw = int(event.passes_accuracy or 0)

        # v2: PASSES_COMPLETED uses above-average threshold
        passes_avg = 0
        if config.passes_avg_by_position:
            try:
                passes_avg = config.passes_avg_by_position.get(group, 0)
            except (KeyError, TypeError):
                passes_avg = 0
        passes_puntuables = max(0, passes_completed_raw - passes_avg)

        raw_stats: dict[ActionType, float] = {
            ActionType.DUELS_WON:        float(event.duels_won or 0),
            ActionType.TACKLES:          float(event.tackles_won or 0),
            ActionType.INTERCEPTIONS:    float(event.interceptions or 0),
            ActionType.BLOCKS:           float(event.blocks or 0),
            ActionType.DRIBBLES_WON:     float(event.dribbles_won or 0),
            ActionType.XA_NO_ASSIST:     float(max(0, (event.passes_key or 0) - a)),
            ActionType.XG_NO_GOAL:       float(max(0, (event.shots_on or 0) - g)),
            ActionType.FOULS_DRAWN:      float(event.fouls_drawn or 0),
            ActionType.PASSES_COMPLETED: float(passes_puntuables),
            ActionType.FOULS_COMMITTED:  float(event.fouls_committed or 0),
            ActionType.YELLOW_CARD:      float(event.cards_yellow or 0),
            ActionType.RED_CARD:         float(event.cards_red or 0),
            ActionType.PENALTY_WON:      float(event.penalty_won or 0),
            ActionType.DRIBBLES_PAST:    float(event.dribbles_past or 0),
        }

        # v2: apply diminishing returns; bifurcate M1 between decisive and accumulative actions
        dr_map = config.diminishing_returns  # may be empty for v1 configs
        decisive_base = 0.0
        accumulative_base = 0.0
        dr_applied: dict[str, dict] = {}
        try:
            group_points = config.base_points[group]
        except KeyError:
            logger.warning(
                "[CalculateScoresForRulesVersionUseCase] No base_points entry for group=%r "
                "rules_version_id=%d — skipping stats event_id=%d",
                group, rules_version_id, event.event_id,
            )
            return None
        for action, count in raw_stats.items():
            base_per_unit = group_points[action]
            if base_per_unit == 0 or count == 0:
                continue
            if action in dr_map:
                pts = DiminishingReturnsConfig.apply(count, float(base_per_unit), dr_map[action])
                dr_applied[action.value] = {
                    "count": count, "cap": dr_map[action].cap,
                    "extra_factor": dr_map[action].extra_factor, "pts": round(pts, 2),
                }
            else:
                pts = float(base_per_unit) * count
            if action in _M1_DECISIVE_STATS_ACTIONS:
                decisive_base += pts
            else:
                accumulative_base += pts

        # Decisive stats (e.g. PENALTY_WON) use full M1; accumulative stats use damped M1_stats
        combined_decisive = max(config.combined_clamp[0], min(
            config.combined_clamp[1], m1_original * m2.value * mrating.value))
        combined_accum = max(config.combined_clamp[0], min(
            config.combined_clamp[1], m1_stats_applied * m2.value * mrating.value))
        base_total = (decisive_base * combined_decisive + accumulative_base * combined_accum) * minutes_scale
        # ELO (M1) already captures opponent quality — competition_weight only for MC bonuses
        comp_name = (competition_name_map or {}).get(event.competition_id, "")
        competition_weight = config.competition_bonus_weights.get(comp_name, 1.0)
        final = round(base_total, 2)
        mc_bonus, mc_audit = self._apply_midfield_bonuses(
            event, group, m2, mrating, config, competition_weight
        )
        if mc_bonus > 0:
            final = round(final + mc_bonus, 2)

        strength_used = (
            getattr(event, "player_team_strength", None) is not None
            and getattr(event, "rival_team_strength", None) is not None
        )

        details = {
            "action": "STATS",
            "position": position.value,
            "base_total": round(base_total, 2),
            "M1": round(m1_original, 3),
            "M2": round(m2.value, 3),
            "stats_m2_attenuation": attenuation,
            "stage_factor_original": event.stage_factor,
            "stage_factor_effective": round(effective_sf, 4),
            "M3": 1.0,
            "M4": 1.0,
            "Mvisit": 1.0,
            "Mrating": round(mrating.value, 2),
            "combined_before_clamp": round(raw, 4),
            "combined_after_clamp": round(combined, 4),
            "m1_source": "team_strength" if strength_used else "legacy_position",
            "m1_original": round(m1_original, 3),
            "m1_stats_weight": weight,
            "m1_stats_applied": round(m1_stats_applied, 3),
            "minutes": minutes,
            "minutes_penalty_applied": minutes_penalty_applied,
            "passes_threshold": passes_avg,
            "passes_puntuables": passes_puntuables,
            "strength_used": strength_used,
            "diminishing_applied": dr_applied,
            "stats_breakdown": {
                k.value: float(v) for k, v in raw_stats.items() if v != 0
            },
            "midfield_bonuses": mc_audit,
            "final_points": final,
        }

        return PlayerEventScore(
            id=None,
            event_id=event.event_id,
            player_id=event.player_id,
            fixture_id=event.fixture_id,
            season=event.season,
            competition_id=event.competition_id,
            rules_version_id=rules_version_id,
            action_type="stats",
            position=position.value,
            base_points=round(base_total, 2),
            m1=round(m1.value, 3),
            m2=round(m2.value, 3),
            m3=1.0,
            m4=1.0,
            mvisit=1.0,
            mrating=round(mrating.value, 2),
            combined_before_clamp=round(raw, 4),
            combined_after_clamp=round(combined, 4),
            final_points=final,
            calculation_details=details,
            created_at=None,
        )

    def _apply_midfield_bonuses(
        self,
        event: PlayerEventRawContextDTO,
        group: PositionGroup,
        m2: M2CompetitionStage,
        mrating: MratingFactor,
        config: ScoringConfig,
        competition_weight: float = 1.0,
    ) -> tuple[float, dict]:
        """Compute MC derived bonuses and return (bonus_pts, audit_dict).

        Returns (0.0, {"enabled": False}) when bonuses are disabled or
        inapplicable, so callers can always unpack safely.
        """
        if not config.enable_midfield_control_bonuses:
            return 0.0, {"enabled": False}

        if group != PositionGroup.MF:
            return 0.0, {"enabled": False}

        minutes = getattr(event, "minutes", None) or 0
        if minutes < _MC_BONUS_MIN_MINUTES:
            return 0.0, {"enabled": False}

        rating = event.rating
        passes_total = event.passes_total or 0
        passes_key = event.passes_key or 0
        tackles_won = event.tackles_won or 0
        interceptions = event.interceptions or 0
        duels_won = event.duels_won or 0

        # passes_accuracy stores completed passes COUNT (not percentage)
        passes_completed = int(event.passes_accuracy or 0)
        passes_accuracy_pct = (passes_completed / passes_total * 100.0) if passes_total > 0 else 0.0
        defensive_actions = tackles_won + interceptions

        control_earned = (
            rating is not None
            and rating >= _MC_CONTROL_MIN_RATING
            and passes_completed >= _MC_CONTROL_MIN_PASSES
            and passes_accuracy_pct >= _MC_CONTROL_MIN_ACCURACY
        )
        two_way_earned = (
            rating is not None
            and rating >= _MC_TWO_WAY_MIN_RATING
            and passes_completed >= _MC_TWO_WAY_MIN_PASSES
            and defensive_actions >= _MC_TWO_WAY_MIN_DEFENSIVE
        )
        creative_earned = (
            rating is not None
            and rating >= _MC_CREATIVE_MIN_RATING
            and passes_completed >= _MC_CREATIVE_MIN_PASSES
            and passes_accuracy_pct >= _MC_CREATIVE_MIN_PASSES_ACCURACY
            and passes_key >= _MC_CREATIVE_MIN_PASSES_KEY
        )

        total_before_cap = (
            (_MC_BONUS_CONTROL if control_earned else 0)
            + (_MC_BONUS_TWO_WAY if two_way_earned else 0)
            + (_MC_BONUS_CREATIVE if creative_earned else 0)
        )

        cap = config.midfield_control_bonus_cap_per_match
        capped = total_before_cap > cap
        mc_bonus_total_base = min(total_before_cap, cap)
        # Intentional: midfield bonuses do not use M1 (only M2 × Mrating × competition_weight)
        mc_bonus_final = mc_bonus_total_base * m2.value * mrating.value * competition_weight

        audit: dict = {
            "enabled": True,
            "position_group": group.value,
            "minutes": minutes,
            "passes_completed": passes_completed,
            "passes_accuracy": round(passes_accuracy_pct, 1),
            "rating": rating,
            "tackles_won": tackles_won,
            "interceptions": interceptions,
            "passes_key": passes_key,
            "duels_won": duels_won,
            "control_midfield_bonus_earned": control_earned,
            "two_way_midfield_bonus_earned": two_way_earned,
            "creative_control_bonus_earned": creative_earned,
            "mc_bonus_total_before_cap": total_before_cap,
            "mc_bonus_cap": cap,
            "mc_bonus_total_base": mc_bonus_total_base,
            "mc_bonus_capped": capped,
            "competition_weight": competition_weight,
            "M2": round(m2.value, 3),
            "Mrating": round(mrating.value, 3),
            "mc_bonus_final": round(mc_bonus_final, 2),
        }
        return mc_bonus_final, audit
