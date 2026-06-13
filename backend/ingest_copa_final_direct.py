"""
Diagnóstico y script de ingesta directa para la Final de Copa del Rey 2024/25
Barcelona (529) vs Real Madrid (541), ext_id=1367758, AET
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from sfa.application.use_cases.ingest_competition import (
    LEAGUES,
    _PlayerAccum,
    _add_to_breakdown,
    _parse_matchday,
)
from sfa.core.config import get_settings
from sfa.domain.position_mapping import map_position
from sfa.domain.scoring.services import BASE_POINTS_TABLE, SFAScoringService
from sfa.domain.scoring.value_objects import (
    ActionType,
    CombinedMultiplier,
    M1RivalDifficulty,
    M2CompetitionStage,
    M3MinuteScore,
    M4ShotDifficulty,
    MvisitFactor,
    SFAScore,
    position_to_group,
)
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.models.enums import EventType, Position
from sfa.infrastructure.providers.api_football import APIFootballProvider
from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

logging.basicConfig(level=logging.WARNING)

FIXTURE_EXT_ID = 1367758
COPA_COMP_ID = 22
SEASON = "2024"
STAGE = "final"
STAGE_FACTOR = 1.3  # Final merece factor mayor que 1.0
BARCELONA_EXT = 529
REAL_MADRID_EXT = 541


def _name_matches(event_name, stats_name):
    if not event_name:
        return False
    a = event_name.lower().strip()
    b = stats_name.lower().strip()
    return a == b or a in b or b in a


async def main():
    settings = get_settings()
    provider = APIFootballProvider(
        api_key=settings.API_FOOTBALL_KEY,
        base_url="https://v3.football.api-sports.io",
    )
    scoring = SFAScoringService()

    async with AsyncSessionLocal() as session:
        repo = IngestionRepository(session)

        print("=== Verificando equipos en DB ===")
        # Ensure both teams exist in the DB
        barcelona_db_id = await repo.upsert_team(BARCELONA_EXT, "Barcelona", COPA_COMP_ID)
        real_madrid_db_id = await repo.upsert_team(REAL_MADRID_EXT, "Real Madrid", COPA_COMP_ID)
        print(f"Barcelona db_id={barcelona_db_id}, Real Madrid db_id={real_madrid_db_id}")

        print("\n=== Insertando fixture ===")
        played_at = datetime(2025, 4, 26, 20, 0, 0, tzinfo=timezone.utc)
        fixture_db_id = await repo.upsert_fixture(
            external_id=FIXTURE_EXT_ID,
            competition_id=COPA_COMP_ID,
            home_team_id=barcelona_db_id,
            away_team_id=real_madrid_db_id,
            stage=STAGE,
            season=SEASON,
            played_at=played_at,
            matchday=None,
        )
        print(f"Fixture insertado: db_id={fixture_db_id}")

        print("\n=== Fetch eventos del partido ===")
        events = await provider.fetch_fixture_events(FIXTURE_EXT_ID)
        print(f"Eventos: {len(events)}")

        # Position cache from La Liga standings (approximate)
        pos_cache = {BARCELONA_EXT: 1, REAL_MADRID_EXT: 2}

        player_accum: dict[int, _PlayerAccum] = {}

        for proc_team_ext_id, proc_team_db_id, rival_ext_id in [
            (BARCELONA_EXT, barcelona_db_id, REAL_MADRID_EXT),
            (REAL_MADRID_EXT, real_madrid_db_id, BARCELONA_EXT),
        ]:
            player_team_pos = pos_cache.get(proc_team_ext_id, 10)
            rival_pos = pos_cache.get(rival_ext_id, 10)
            is_away = (proc_team_ext_id == REAL_MADRID_EXT)

            print(f"\n=== Procesando equipo ext_id={proc_team_ext_id} ===")
            player_stats_list = await provider.fetch_fixture_players(FIXTURE_EXT_ID, proc_team_ext_id)
            print(f"  Players con stats: {len(player_stats_list)}")

            for ps in player_stats_list:
                if ps.minutes < 1:
                    continue

                position = map_position(ps.player_name, ps.position)
                player_db_id = await repo.upsert_player(
                    ps.player_external_id, ps.player_name, proc_team_db_id, position,
                )

                if player_db_id not in player_accum:
                    player_accum[player_db_id] = _PlayerAccum()
                accum = player_accum[player_db_id]
                accum.matches_played += 1
                accum.real_goals += ps.goals
                accum.real_assists += ps.assists
                accum.total_minutes += ps.minutes

                await repo.upsert_player_stats(
                    player_db_id, fixture_db_id, SEASON,
                    {
                        "goals": ps.goals, "assists": ps.assists,
                        "shots_on": ps.shots_on, "passes_key": ps.passes_key,
                        "dribbles_won": ps.dribbles_success, "duels_won": ps.duels_won,
                        "tackles_won": ps.tackles, "interceptions": ps.interceptions,
                        "blocks": ps.blocks, "fouls_drawn": ps.fouls_drawn,
                        "clearances": ps.clearances, "dribbles_attempts": ps.dribbles_attempts,
                        "minutes": ps.minutes,
                    },
                )

                if position == Position.GK:
                    continue

                group = position_to_group(position)
                await repo.delete_player_events_for_fixture(player_db_id, fixture_db_id)

                # Goals
                player_goals = [
                    e for e in events
                    if e.type == "Goal"
                    and e.detail not in ("Missed Penalty", "Own Goal")
                    and _name_matches(e.player_name, ps.player_name)
                    and e.team_external_id == proc_team_ext_id
                ]
                for goal_evt in player_goals:
                    minute = goal_evt.minute + goal_evt.extra_minute
                    db_minute = max(1, min(120, minute))
                    clamped = max(1, min(90, minute))
                    is_penalty = goal_evt.detail == "Penalty"
                    is_shootout = is_penalty and minute > 120

                    home_b, away_b = provider.get_score_at_minute(events, minute, BARCELONA_EXT)
                    score_diff = (away_b - home_b) if is_away else (home_b - away_b)
                    score_before_str = f"{home_b}:{away_b}"

                    if is_shootout:
                        action = ActionType.GOAL_SHOOTOUT
                        psxg = 0.75
                        event_type = EventType.GOAL_SHOOTOUT
                    else:
                        action = ActionType.GOAL_PENALTY if is_penalty else ActionType.GOAL
                        psxg = 0.32
                        event_type = EventType.GOAL_PENALTY if is_penalty else EventType.GOAL

                    m1 = M1RivalDifficulty(player_team_pos, rival_pos)
                    m2 = M2CompetitionStage(STAGE_FACTOR)
                    m3 = M3MinuteScore(clamped, score_diff, is_penalty, is_shootout=is_shootout)
                    m4 = M4ShotDifficulty(psxg)
                    mvisit = MvisitFactor(is_away, True)
                    combined = CombinedMultiplier(m1, m2, m3, m4, mvisit)
                    sfa = SFAScore(float(BASE_POINTS_TABLE[group][action]), combined)

                    await repo.upsert_player_event(
                        player_db_id, fixture_db_id,
                        db_minute, event_type,
                        score_before_str, score_diff, psxg,
                        m1.value, m2.value, m3.value, m4.value, mvisit.value,
                        round(sfa.total, 2),
                    )
                    _add_to_breakdown(accum.breakdown, action.value, sfa.total)
                    accum.total_pts += sfa.total

                    if ps.player_name == "Lamine Yamal" or "Yamal" in ps.player_name:
                        print(f"  Yamal GOL min={minute}, pts={round(sfa.total)}")

                # Assists
                player_assists = [
                    e for e in events
                    if e.type == "Goal"
                    and e.detail not in ("Missed Penalty", "Own Goal")
                    and e.assist_name is not None
                    and _name_matches(e.assist_name, ps.player_name)
                    and e.team_external_id == proc_team_ext_id
                ]
                for assist_evt in player_assists:
                    minute = assist_evt.minute + assist_evt.extra_minute
                    db_minute = max(1, min(120, minute))
                    clamped = max(1, min(90, minute))
                    is_penalty = assist_evt.detail == "Penalty"

                    home_b, away_b = provider.get_score_at_minute(events, minute, BARCELONA_EXT)
                    score_diff = (away_b - home_b) if is_away else (home_b - away_b)
                    score_before_str = f"{home_b}:{away_b}"

                    is_corner = "corner" in assist_evt.detail.lower()
                    action = ActionType.CORNER_ASSIST if is_corner else ActionType.ASSIST
                    event_type = EventType.CORNER_ASSIST if is_corner else EventType.ASSIST

                    m1 = M1RivalDifficulty(player_team_pos, rival_pos)
                    m2 = M2CompetitionStage(STAGE_FACTOR)
                    m3 = M3MinuteScore(clamped, score_diff, is_penalty)
                    m4 = M4ShotDifficulty(None)
                    mvisit = MvisitFactor(is_away, True)
                    combined = CombinedMultiplier(m1, m2, m3, m4, mvisit)
                    sfa = SFAScore(float(BASE_POINTS_TABLE[group][action]), combined)

                    await repo.upsert_player_event(
                        player_db_id, fixture_db_id,
                        db_minute, event_type,
                        score_before_str, score_diff, None,
                        m1.value, m2.value, m3.value, m4.value, mvisit.value,
                        round(sfa.total, 2),
                    )
                    _add_to_breakdown(accum.breakdown, action.value, sfa.total)
                    accum.total_pts += sfa.total

                # Match stats
                stats_for_scoring = {
                    ActionType.DUELS_WON: ps.duels_won,
                    ActionType.TACKLES_INTERCEPTIONS: ps.tackles + ps.interceptions,
                    ActionType.BLOCKS: ps.blocks,
                    ActionType.DRIBBLES_WON: ps.dribbles_success,
                    ActionType.XA_NO_ASSIST: max(0, ps.passes_key - ps.assists),
                    ActionType.XG_NO_GOAL: max(0, ps.shots_on - ps.goals),
                    ActionType.FOULS_DRAWN: ps.fouls_drawn,
                    ActionType.CLEARANCES: ps.clearances,
                }
                stat_scores = scoring.score_match_stats(
                    group, stats_for_scoring, player_team_pos, rival_pos, STAGE_FACTOR,
                )
                for s_score in stat_scores:
                    accum.total_pts += s_score.total
                    _add_to_breakdown(accum.breakdown, "stats", s_score.total)

                stats_pts = round(sum(s.total for s in stat_scores), 2)
                m1_val = M1RivalDifficulty(player_team_pos, rival_pos).value
                await repo.upsert_player_event(
                    player_id=player_db_id,
                    fixture_id=fixture_db_id,
                    minute=90,
                    event_type=EventType.STATS,
                    score_before=None,
                    score_diff=None,
                    psxg=None,
                    m1=m1_val,
                    m2=STAGE_FACTOR,
                    m3=1.0,
                    m4=1.0,
                    mvisit=1.0,
                    pts=stats_pts,
                )

        # Update season scores
        print("\n=== Actualizando SFASeasonScore ===")
        for player_db_id, accum in player_accum.items():
            if accum.total_minutes < 90:
                continue
            total = accum.total_pts
            for key in accum.breakdown:
                pct = round(accum.breakdown[key]["pts"] / total * 100, 1) if total > 0 else 0.0
                accum.breakdown[key]["pct"] = pct
            await repo.upsert_season_score(
                player_db_id, COPA_COMP_ID, SEASON,
                round(accum.total_pts, 2),
                accum.matches_played,
                accum.breakdown,
            )

        await session.commit()
        print(f"\nCommit OK. Jugadores con >=90 min procesados: {sum(1 for a in player_accum.values() if a.total_minutes >= 90)}")

        # Verify Yamal
        print("\n=== Verificando Yamal en Copa del Rey ===")
        from sqlalchemy import text
        r = await session.execute(text("""
            SELECT f.played_at::date, f.stage, ps.minutes, ps.goals
            FROM player_stats ps
            JOIN fixtures f ON ps.fixture_id=f.id
            WHERE ps.player_id=34 AND f.competition_id=22 AND f.season='2024'
            ORDER BY f.played_at
        """))
        for row in r.fetchall():
            print(f"  {row[0]} | {row[1]} | mins={row[2]} | goals={row[3]}")


asyncio.run(main())
