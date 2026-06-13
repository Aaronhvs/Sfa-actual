from __future__ import annotations

import logging
from collections import defaultdict

from sfa.domain.enrichment_ports import (
    EnrichmentRepositoryPort,
    RecalculationResult,
)
from sfa.domain.scoring.services import BASE_POINTS_TABLE
from sfa.domain.scoring.value_objects import (
    ActionType,
    M4ShotDifficulty,
    MratingFactor,
    PositionGroup,
    position_to_group,
)
from sfa.infrastructure.models.enums import Position

logger = logging.getLogger(__name__)

# v2 groups not present in BASE_POINTS_TABLE (v1 legacy) — map to nearest v1 group
_V2_TO_V1_GROUP: dict[PositionGroup, PositionGroup] = {
    PositionGroup.DEL: PositionGroup.FW,
    PositionGroup.EXT: PositionGroup.FW,
    PositionGroup.LAT: PositionGroup.DF,
    PositionGroup.DC:  PositionGroup.DF,
}


def _reconcile_breakdown_counts(breakdown: dict, real_goals: int, real_assists: int) -> None:
    event_goals = (
        breakdown.get("goal", {}).get("count", 0)
        + breakdown.get("goal_penalty", {}).get("count", 0)
    )
    missing_goals = real_goals - event_goals
    if missing_goals > 0:
        if "goal" not in breakdown:
            breakdown["goal"] = {"count": 0, "pts": 0.0}
        breakdown["goal"]["count"] += missing_goals

    event_assists = (
        breakdown.get("assist", {}).get("count", 0)
        + breakdown.get("corner_assist", {}).get("count", 0)
    )
    missing_assists = real_assists - event_assists
    if missing_assists > 0:
        if "assist" not in breakdown:
            breakdown["assist"] = {"count": 0, "pts": 0.0}
        breakdown["assist"]["count"] += missing_assists



class RecalculateScoresUseCase:
    def __init__(self, repo: EnrichmentRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, competition_id: int, season: str) -> RecalculationResult:
        events_updated = 0
        scores_updated = 0
        player_deltas: dict[int, float] = defaultdict(float)

        # ── Phase 1: Goal / penalty events (psxg IS NOT NULL) ──────────────
        goal_events = await self._repo.get_events_with_psxg_for_recalc(
            competition_id, season
        )
        for event in goal_events:
            try:
                position = Position(event.player_position)
                group = _V2_TO_V1_GROUP.get(position_to_group(position), position_to_group(position))
                action = ActionType(event.event_type)
            except ValueError as exc:
                logger.warning("RecalcGoal: skipping event %d — %s", event.id, exc)
                continue

            m4 = M4ShotDifficulty(psxg=event.psxg).value
            raw = event.m1 * event.m2 * event.m3 * m4 * event.mvisit
            combined = max(0.3, min(4.0, raw))
            new_pts = round(float(BASE_POINTS_TABLE[group][action]) * combined, 2)

            if abs(new_pts - event.current_pts) > 0.01:
                await self._repo.update_event_scores(event.id, m4=m4, pts=new_pts)
                player_deltas[event.player_id] += new_pts - event.current_pts
                events_updated += 1

        # ── Phase 2: Stats events (one row per player per fixture) ──────────
        stats_events = await self._repo.get_stats_events_for_recalc(
            competition_id, season
        )
        for event in stats_events:
            try:
                position = Position(event.player_position)
                group = _V2_TO_V1_GROUP.get(position_to_group(position), position_to_group(position))
            except ValueError as exc:
                logger.warning("RecalcStats: skipping event %d — %s", event.event_id, exc)
                continue

            stat_counts = {
                ActionType.DUELS_WON:             event.duels_won,
                ActionType.TACKLES:               event.tackles_won,
                ActionType.INTERCEPTIONS:         event.interceptions,
                ActionType.BLOCKS:                event.blocks,
                ActionType.DRIBBLES_WON:          event.dribbles_won,
                ActionType.XA_NO_ASSIST:          max(0, event.passes_key - event.assists),
                ActionType.XG_NO_GOAL:            max(0, event.shots_on - event.goals),
                ActionType.FOULS_DRAWN:           event.fouls_drawn,
                ActionType.PASSES_COMPLETED:      int(event.passes_total * event.passes_accuracy / 100),
                ActionType.FOULS_COMMITTED:       event.fouls_committed,
                ActionType.YELLOW_CARD:           event.cards_yellow,
                ActionType.RED_CARD:              event.cards_red,
                ActionType.PENALTY_WON:           event.penalty_won,
                ActionType.DRIBBLES_PAST:         event.dribbles_past,
            }

            mrating = MratingFactor(event.rating)
            combined = max(0.3, min(4.0, event.m1 * event.m2 * mrating.value))
            new_pts = round(sum(
                float(BASE_POINTS_TABLE[group][action]) * count * combined
                for action, count in stat_counts.items()
                if BASE_POINTS_TABLE[group][action] != 0 and count != 0
            ), 2)

            if abs(new_pts - event.current_pts) > 0.01:
                await self._repo.update_event_pts(event.event_id, new_pts, m2=event.m2)
                player_deltas[event.player_id] += new_pts - event.current_pts
                events_updated += 1

        # ── Phase 3: Rebuild season scores for affected players ─────────────
        for player_id, delta in player_deltas.items():
            current = await self._repo.get_player_season_score_row(
                player_id, competition_id, season
            )
            if current is None:
                logger.warning(
                    "RecalcScore: no season_score for player_id=%d comp=%d season=%s",
                    player_id, competition_id, season,
                )
                continue

            new_total_pts = round(current.total_pts + delta, 2)

            # Rebuild breakdown from all events, normalising keys to lowercase
            all_events = await self._repo.get_all_player_season_events(
                player_id, competition_id, season
            )
            new_breakdown: dict[str, dict] = {}
            for evt in all_events:
                key = evt.event_type.lower()
                if key not in new_breakdown:
                    new_breakdown[key] = {"count": 0, "pts": 0.0}
                new_breakdown[key]["count"] += 1
                new_breakdown[key]["pts"] = round(
                    new_breakdown[key]["pts"] + evt.pts, 2
                )

            # Reconciliar conteos con stats reales de PlayerStats
            real_goals, real_assists = await self._repo.get_player_season_real_stats(
                player_id, competition_id, season
            )
            _reconcile_breakdown_counts(new_breakdown, real_goals, real_assists)

            for key in new_breakdown:
                pct = (
                    round(new_breakdown[key]["pts"] / new_total_pts * 100, 1)
                    if new_total_pts > 0 else 0.0
                )
                new_breakdown[key]["pct"] = pct

            await self._repo.update_season_score(
                player_id=player_id,
                competition_id=competition_id,
                season=season,
                total_pts=new_total_pts,
                matches_played=current.matches_played,
                breakdown=new_breakdown,
            )
            scores_updated += 1

        logger.info(
            "RecalculateScores: events_updated=%d scores_updated=%d "
            "comp=%d season=%s",
            events_updated, scores_updated, competition_id, season,
        )
        return RecalculationResult(
            events_updated=events_updated,
            scores_updated=scores_updated,
        )
