from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.ingestion_ports import (
    FixtureEventRawDTO,
    FootballDataProviderPort,
    IngestionRepositoryPort,
)
from sfa.domain.name_matching import name_matches
from sfa.domain.scoring.services import (
    ScoreTimeline,
    ShootoutDecider,
    is_missed_penalty_event,
    is_penalty_attempt_event,
    is_shootout_attempt_event,
)
from sfa.domain.scoring_ports import ScoringRulesVersionRepositoryPort
from sfa.infrastructure.models.enums import EventType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReingestPlayerResult:
    player_id: int
    season: str
    fixtures_reingested: int
    events_ingested: int
    scores_recalculated: int
    status: str
    error: str | None


def _map_event_type(type_str: str, detail_str: str) -> EventType | None:
    """Map API-Football event strings to EventType. Returns None for irrelevant events."""
    if type_str != "Goal":
        return None
    if detail_str in ("Missed Penalty", "Own Goal"):
        return None

    minute_hint = None  # resolved at call site
    if detail_str == "Penalty":
        return EventType.GOAL_PENALTY
    return EventType.GOAL


def _map_assist_type(detail_str: str) -> EventType:
    if "corner" in detail_str.lower():
        return EventType.CORNER_ASSIST
    return EventType.ASSIST


class ReingestPlayerUseCase:
    """Re-ingest goal/assist events for a single player and recalculate their scores.

    Fetches fixture events from the API for each fixture the player already
    participated in (per player_stats), deletes their existing player_events, and
    re-upserts the goal/assist events. Then triggers a targeted recalculation of
    that player's scores only.
    """

    def __init__(
        self,
        provider: FootballDataProviderPort,
        ingestion_repo: IngestionRepositoryPort,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
        scoring_use_case: object,
    ) -> None:
        self._provider = provider
        self._ingestion_repo = ingestion_repo
        self._rules_version_repo = rules_version_repo
        self._scoring_use_case = scoring_use_case

    async def execute(
        self,
        player_id: int,
        season: int,
        competition_id: int | None = None,
    ) -> ReingestPlayerResult:
        season_str = str(season)

        active_version = await self._rules_version_repo.get_active_version()
        if active_version is None:
            return ReingestPlayerResult(
                player_id=player_id,
                season=season_str,
                fixtures_reingested=0,
                events_ingested=0,
                scores_recalculated=0,
                status="failed",
                error="no active rules version",
            )

        fixtures = await self._ingestion_repo.get_fixtures_for_player(
            player_id, season_str, competition_id
        )
        if not fixtures:
            logger.warning(
                "[ReingestPlayerUseCase] No fixtures found for player_id=%d season=%s",
                player_id, season_str,
            )
            return ReingestPlayerResult(
                player_id=player_id,
                season=season_str,
                fixtures_reingested=0,
                events_ingested=0,
                scores_recalculated=0,
                status="no_fixtures",
                error=None,
            )

        player_name = fixtures[0].player_name
        player_external_id = fixtures[0].player_external_id
        logger.info(
            "[ReingestPlayerUseCase] START player_id=%d name=%r external_id=%d "
            "season=%s fixtures=%d",
            player_id, player_name, player_external_id, season_str, len(fixtures),
        )

        events_ingested = 0

        for row in fixtures:
            is_away = row.player_team_id == row.away_team_id

            raw_events = await self._provider.fetch_fixture_events(row.fixture_external_id)
            if (
                row.home_team_external_id is None
                or row.away_team_external_id is None
                or row.player_team_external_id
                not in (row.home_team_external_id, row.away_team_external_id)
            ):
                raise ValueError(
                    "Missing or invalid external team IDs for fixture "
                    f"{row.fixture_external_id}"
                )
            score_timeline = ScoreTimeline.build(
                row.home_team_external_id,
                row.away_team_external_id,
                raw_events,
            )
            decisive_shootout_ids = ShootoutDecider.decisive_event_ids(
                row.home_team_external_id,
                row.away_team_external_id,
                raw_events,
            )
            pending_events: list[tuple[FixtureEventRawDTO, bool, bool]] = []

            for evt in raw_events:
                is_goal_for_player = (
                    evt.type == "Goal"
                    and evt.detail not in ("Own Goal",)
                    and name_matches(evt.player_name, player_name)
                    and (
                        not is_missed_penalty_event(evt)
                        or is_shootout_attempt_event(evt)
                    )
                )
                is_assist_for_player = (
                    evt.type == "Goal"
                    and evt.detail not in ("Missed Penalty", "Own Goal")
                    and not is_shootout_attempt_event(evt)
                    and evt.assist_name is not None
                    and name_matches(evt.assist_name, player_name)
                )

                if not is_goal_for_player and not is_assist_for_player:
                    continue
                pending_events.append(
                    (evt, is_goal_for_player, is_assist_for_player)
                )

            await self._ingestion_repo.delete_player_events_for_fixture(
                player_id, row.fixture_id
            )

            for evt, is_goal_for_player, is_assist_for_player in pending_events:
                minute = evt.minute + evt.extra_minute
                db_minute = max(1, min(120, minute))

                if is_goal_for_player:
                    is_penalty = is_penalty_attempt_event(evt)
                    is_missed_penalty = is_missed_penalty_event(evt)
                    is_shootout = is_shootout_attempt_event(evt)
                    if is_shootout:
                        score_diff = 0
                        score_before_str = None
                    else:
                        transition = score_timeline.transition_for(evt)
                        home_b, away_b = transition.home_before, transition.away_before
                        score_diff = (away_b - home_b) if is_away else (home_b - away_b)
                        score_before_str = f"{home_b}:{away_b}"
                    if is_shootout:
                        is_decisive = id(evt) in decisive_shootout_ids
                        if is_missed_penalty:
                            event_type = (
                                EventType.MISSED_SHOOTOUT_DECISIVE
                                if is_decisive
                                else EventType.MISSED_SHOOTOUT
                            )
                        else:
                            event_type = (
                                EventType.GOAL_SHOOTOUT_DECISIVE
                                if is_decisive
                                else EventType.GOAL_SHOOTOUT
                            )
                        psxg: float | None = None
                    elif is_penalty:
                        event_type = EventType.GOAL_PENALTY
                        psxg = None
                    else:
                        event_type = EventType.GOAL
                        psxg = None
                else:
                    transition = score_timeline.transition_for(evt)
                    home_b, away_b = transition.home_before, transition.away_before
                    score_diff = (away_b - home_b) if is_away else (home_b - away_b)
                    score_before_str = f"{home_b}:{away_b}"
                    is_corner = "corner" in evt.detail.lower()
                    event_type = EventType.CORNER_ASSIST if is_corner else EventType.ASSIST
                    psxg = None

                await self._ingestion_repo.upsert_player_event(
                    player_id=player_id,
                    fixture_id=row.fixture_id,
                    team_id=row.player_team_id,
                    minute=db_minute,
                    event_type=event_type,
                    score_before=score_before_str,
                    score_diff=score_diff,
                    psxg=psxg,
                    m1=1.0, m2=1.0, m3=1.0, m4=1.0, mvisit=1.0,
                    pts=0.0,
                    player_team_pos=None,
                    rival_team_pos=None,
                    is_away=is_away,
                )
                events_ingested += 1

            # Re-fetch stats for this player from the fixture (refreshes STATS event)
            all_stats = await self._provider.fetch_all_fixture_players(row.fixture_external_id)
            player_stats = next(
                (s for s in all_stats if s.player_external_id == player_external_id),
                None,
            )
            if player_stats:
                await self._ingestion_repo.upsert_player_stats(
                    player_id,
                    row.fixture_id,
                    row.player_team_id,
                    season_str,
                    {
                        "goals": player_stats.goals,
                        "assists": player_stats.assists,
                        "shots_on": player_stats.shots_on,
                        "shots_total": player_stats.shots_total,
                        "passes_key": player_stats.passes_key,
                        "passes_total": player_stats.passes_total,
                        "passes_accuracy": player_stats.passes_accuracy,
                        "dribbles_won": player_stats.dribbles_success,
                        "dribbles_attempts": player_stats.dribbles_attempts,
                        "dribbles_past": player_stats.dribbles_past,
                        "duels_won": player_stats.duels_won,
                        "duels_total": player_stats.duels_total,
                        "tackles_won": player_stats.tackles,
                        "interceptions": player_stats.interceptions,
                        "blocks": player_stats.blocks,
                        "fouls_drawn": player_stats.fouls_drawn,
                        "fouls_committed": player_stats.fouls_committed,
                        "cards_yellow": player_stats.cards_yellow,
                        "cards_red": player_stats.cards_red,
                        "penalty_won": player_stats.penalty_won,
                        "saves": player_stats.saves,
                        "goals_conceded": player_stats.goals_conceded,
                        "minutes": player_stats.minutes,
                        "rating": player_stats.rating,
                    },
                )
                # Re-upsert the STATS player_event so it's not deleted
                await self._ingestion_repo.upsert_player_event(
                    player_id=player_id,
                    fixture_id=row.fixture_id,
                    team_id=row.player_team_id,
                    minute=90,
                    event_type=EventType.STATS,
                    score_before=None,
                    score_diff=None,
                    psxg=None,
                    m1=1.0, m2=1.0, m3=1.0, m4=1.0, mvisit=1.0,
                    pts=0.0,
                    player_team_pos=None,
                    rival_team_pos=None,
                    is_away=is_away,
                )

        logger.info(
            "[ReingestPlayerUseCase] Reingested %d fixtures, %d events for player_id=%d",
            len(fixtures), events_ingested, player_id,
        )

        scoring_result = await self._scoring_use_case.execute(
            rules_version_id=active_version.id,
            season=season_str,
            competition_id=competition_id,
            player_id=player_id,
            force_recalculate=True,
        )

        logger.info(
            "[ReingestPlayerUseCase] Scoring complete: events_calculated=%d status=%s",
            scoring_result.events_calculated, scoring_result.status,
        )

        return ReingestPlayerResult(
            player_id=player_id,
            season=season_str,
            fixtures_reingested=len(fixtures),
            events_ingested=events_ingested,
            scores_recalculated=scoring_result.events_calculated,
            status="ok",
            error=None,
        )
