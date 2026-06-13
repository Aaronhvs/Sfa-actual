"""
Ingest specific World Cup fixtures by their API-Football fixture ID.
Used when the standings API doesn't return teams yet (matches played before
the standings endpoint updates).

Usage:
    python scripts/ingest_fixtures_by_id.py 1539000 1489370 1489373
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def _ingest_fixture(
    fixture_ext_id: int,
    provider,
    repo,
    competition_id: int,
) -> int:
    """Process a single fixture. Returns 1 if processed, 0 if skipped."""
    from sfa.application.use_cases.ingest_competition import _validate_appearance_team, _parse_matchday
    from sfa.domain.name_matching import name_matches as _name_matches
    from sfa.domain.position_mapping import KNOWN_POSITIONS, map_position
    from sfa.domain.scoring.value_objects import position_to_group
    from sfa.infrastructure.models.enums import EventType, IngestionStatus, Position

    data = await provider._get("fixtures", {"id": str(fixture_ext_id)})
    responses = data.get("response", [])
    if not responses:
        logger.warning("No fixture data for id=%s", fixture_ext_id)
        return 0

    f = responses[0]
    fixture_info = f["fixture"]
    teams_info = f["teams"]
    goals_info = f["goals"]

    status = fixture_info["status"]["short"]
    if status not in ("FT", "AET", "PEN"):
        logger.info("Skipping fixture %s — status=%s (not finished)", fixture_ext_id, status)
        return 0

    home_ext_id = teams_info["home"]["id"]
    home_name = teams_info["home"]["name"]
    away_ext_id = teams_info["away"]["id"]
    away_name = teams_info["away"]["name"]
    round_str = f["league"]["round"]
    played_at = datetime.fromisoformat(fixture_info["date"].replace("Z", "+00:00"))
    stage = provider.get_stage(round_str, f["league"]["name"])
    matchday = _parse_matchday(round_str)
    season_str = str(f["league"]["season"])

    home_db_id = await repo.upsert_team(home_ext_id, home_name, competition_id)
    away_db_id = await repo.upsert_team(away_ext_id, away_name, competition_id)
    stage_factor = await repo.get_stage_factor(competition_id, stage)

    fixture_db_id = await repo.upsert_fixture(
        fixture_ext_id, competition_id,
        home_db_id, away_db_id,
        stage, season_str, played_at, matchday,
    )

    events = await provider.fetch_fixture_events(fixture_ext_id)

    for proc_ext_id, proc_db_id, rival_ext_id in [
        (home_ext_id, home_db_id, away_ext_id),
        (away_ext_id, away_db_id, home_ext_id),
    ]:
        is_away = proc_ext_id == away_ext_id
        player_team_pos = 10   # sin standings aún — fallback
        rival_pos = 10

        player_stats_list = await provider.fetch_fixture_players(fixture_ext_id, proc_ext_id)
        _validate_appearance_team(fixture_db_id, proc_db_id, home_db_id, away_db_id)

        for ps in player_stats_list:
            if ps.minutes < 1:
                continue
            if ps.player_external_id <= 0:
                continue

            position = map_position(ps.player_name, ps.position)
            update_pos = ps.player_name in KNOWN_POSITIONS or position != Position.MC
            player_db_id = await repo.upsert_player(
                ps.player_external_id, ps.player_name,
                position,
                photo_url=ps.photo_url,
                update_position=update_pos,
            )

            await repo.upsert_player_stats(
                player_db_id, fixture_db_id, proc_db_id, season_str,
                {
                    "goals": ps.goals, "assists": ps.assists,
                    "shots_on": ps.shots_on, "shots_total": ps.shots_total,
                    "passes_key": ps.passes_key, "passes_total": ps.passes_total,
                    "passes_accuracy": ps.passes_accuracy,
                    "dribbles_won": ps.dribbles_success,
                    "dribbles_attempts": ps.dribbles_attempts,
                    "dribbles_past": ps.dribbles_past,
                    "duels_won": ps.duels_won, "duels_total": ps.duels_total,
                    "tackles_won": ps.tackles, "interceptions": ps.interceptions,
                    "blocks": ps.blocks, "fouls_drawn": ps.fouls_drawn,
                    "fouls_committed": ps.fouls_committed,
                    "cards_yellow": ps.cards_yellow, "cards_red": ps.cards_red,
                    "penalty_won": ps.penalty_won, "saves": ps.saves,
                    "goals_conceded": ps.goals_conceded,
                    "minutes": ps.minutes, "rating": ps.rating,
                },
            )

            if position == Position.GK:
                continue

            group = position_to_group(position)
            await repo.delete_player_events_for_fixture(player_db_id, fixture_db_id)

            player_goals = [
                e for e in events
                if e.type == "Goal"
                and e.detail not in ("Missed Penalty", "Own Goal")
                and _name_matches(e.player_name, ps.player_name)
                and e.team_external_id == proc_ext_id
            ]
            for goal_evt in player_goals:
                minute = goal_evt.minute + goal_evt.extra_minute
                db_minute = max(1, min(120, minute))
                clamped = max(1, min(90, minute))
                is_penalty = goal_evt.detail == "Penalty"
                is_shootout = is_penalty and minute > 120
                home_b, away_b = provider.get_score_at_minute(events, minute, home_ext_id)
                score_diff = (away_b - home_b) if is_away else (home_b - away_b)
                psxg = 0.75 if is_shootout else 0.32
                event_type = (
                    EventType.GOAL_SHOOTOUT if is_shootout
                    else EventType.GOAL_PENALTY if is_penalty
                    else EventType.GOAL
                )
                await repo.upsert_player_event(
                    player_db_id, fixture_db_id, proc_db_id,
                    db_minute, event_type,
                    f"{home_b}:{away_b}", score_diff, psxg,
                    1.0, 1.0, 1.0, 1.0, 1.0, 0.0,
                    player_team_pos=player_team_pos,
                    rival_team_pos=rival_pos,
                    is_away=is_away,
                )

            player_assists = [
                e for e in events
                if e.type == "Goal"
                and e.detail not in ("Missed Penalty", "Own Goal")
                and e.assist_name is not None
                and _name_matches(e.assist_name, ps.player_name)
                and e.team_external_id == proc_ext_id
            ]
            for assist_evt in player_assists:
                minute = assist_evt.minute + assist_evt.extra_minute
                db_minute = max(1, min(120, minute))
                is_corner = "corner" in assist_evt.detail.lower()
                home_b, away_b = provider.get_score_at_minute(events, minute, home_ext_id)
                score_diff = (away_b - home_b) if is_away else (home_b - away_b)
                event_type = EventType.CORNER_ASSIST if is_corner else EventType.ASSIST
                await repo.upsert_player_event(
                    player_db_id, fixture_db_id, proc_db_id,
                    db_minute, event_type,
                    f"{home_b}:{away_b}", score_diff, None,
                    1.0, 1.0, 1.0, 1.0, 1.0, 0.0,
                    player_team_pos=player_team_pos,
                    rival_team_pos=rival_pos,
                    is_away=is_away,
                )

            await repo.upsert_player_event(
                player_db_id, fixture_db_id, proc_db_id,
                90, EventType.STATS, None, None, None,
                1.0, 1.0, 1.0, 1.0, 1.0, 0.0,
                player_team_pos=player_team_pos,
                rival_team_pos=rival_pos,
                is_away=is_away,
            )

    logger.info(
        "Fixture %s ingested: %s %s-%s %s",
        fixture_ext_id, home_name,
        goals_info["home"], goals_info["away"],
        away_name,
    )
    return 1


async def main(fixture_ids: list[int]) -> None:
    from sfa.core.config import get_settings
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.models.competitions.models import Competition
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository
    from sqlalchemy import select

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    provider = APIFootballProvider(settings.API_FOOTBALL_KEY, settings.API_FOOTBALL_BASE_URL)

    async with AsyncSessionLocal() as session:
        competition_id = await session.scalar(
            select(Competition.id).where(Competition.name == "World Cup")
        )
        if competition_id is None:
            logger.error("World Cup competition not found in DB — run WC ingestion first")
            return

        repo = IngestionRepository(session)
        processed = 0
        for fid in fixture_ids:
            processed += await _ingest_fixture(fid, provider, repo, competition_id)

        await session.commit()
        logger.info("Done — %d/%d fixtures ingested", processed, len(fixture_ids))

    if processed > 0:
        from sfa.infrastructure.database import AsyncSessionLocal as S2
        from sfa.infrastructure.repositories.scoring_rules_version_repository import ScoringRulesVersionRepository
        async with S2() as ver_session:
            active = await ScoringRulesVersionRepository(ver_session).get_active_version()
        if active:
            from sfa.tasks.run_full_recalculation_task import run_full_recalculation_task
            run_full_recalculation_task.delay(
                rules_version_id=active.id, season="2026", force_recalculate=True
            )
            logger.info("Queued recalculation for season 2026 rules_version_id=%d", active.id)


if __name__ == "__main__":
    ids = [int(x) for x in sys.argv[1:]]
    if not ids:
        print("Usage: python ingest_fixtures_by_id.py <fixture_id> [fixture_id ...]")
        sys.exit(1)
    asyncio.run(main(ids))
