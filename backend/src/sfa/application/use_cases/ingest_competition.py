from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sfa.domain.ingestion_ports import (
    FixtureEventRawDTO,
    FootballDataProviderPort,
    IngestionRepositoryPort,
)
from sfa.domain.name_matching import name_matches as _name_matches
from sfa.domain.position_mapping import KNOWN_POSITIONS, map_position
from sfa.domain.scoring.services import ScoreTimeline
from sfa.domain.scoring.value_objects import position_to_group
from sfa.infrastructure.models.enums import EventType, IngestionStatus, Position

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# League configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeagueConfig:
    id: int
    name: str
    country: str
    comp_factor: float
    top_n: int | None = None  # None = all teams
    standings_league_id: int | None = None  # borrow standings from another league (cups)
    participant_kind: str = "club"


@dataclass(frozen=True)
class IngestionResult:
    competition: str
    players_processed: int
    fixtures_processed: int
    status: str
    error: str | None


LEAGUES: list[LeagueConfig] = [
    # ── Torneos internacionales ─────────────────────────────────────────────
    LeagueConfig(id=1,   name="World Cup",            country="INT", comp_factor=1.75, participant_kind="national_team"),
    # ── Ligas principales ───────────────────────────────────────────────────
    LeagueConfig(id=140, name="La Liga",              country="ESP", comp_factor=1.0),
    LeagueConfig(id=39,  name="Premier League",       country="ENG", comp_factor=1.0),
    LeagueConfig(id=78,  name="Bundesliga",           country="GER", comp_factor=1.0),
    LeagueConfig(id=135, name="Serie A",              country="ITA", comp_factor=1.0),
    LeagueConfig(id=61,  name="Ligue 1",              country="FRA", comp_factor=1.0),
    # ── UEFA ────────────────────────────────────────────────────────────────
    LeagueConfig(id=2,   name="Champions League",     country="EUR", comp_factor=1.5),
    LeagueConfig(id=3,   name="Europa League",        country="EUR", comp_factor=1.3),
    LeagueConfig(id=848, name="Conference League",    country="EUR", comp_factor=1.1),
    LeagueConfig(id=531, name="UEFA Super Cup",       country="EUR", comp_factor=1.05, standings_league_id=2),
    # ── Copas nacionales ────────────────────────────────────────────────────
    LeagueConfig(id=143, name="Copa del Rey",         country="ESP", comp_factor=1.0,  standings_league_id=140),
    LeagueConfig(id=556, name="Supercopa de España",  country="ESP", comp_factor=1.1,  standings_league_id=140),
    LeagueConfig(id=45,  name="FA Cup",               country="ENG", comp_factor=1.0,  standings_league_id=39),
    LeagueConfig(id=48,  name="EFL Cup",              country="ENG", comp_factor=0.85, standings_league_id=39),
    LeagueConfig(id=528, name="Community Shield",     country="ENG", comp_factor=0.75, standings_league_id=39),
    LeagueConfig(id=81,  name="DFB-Pokal",            country="GER", comp_factor=1.0,  standings_league_id=78),
    LeagueConfig(id=529, name="DFL-Supercup",         country="GER", comp_factor=0.85, standings_league_id=78),
    LeagueConfig(id=137, name="Coppa Italia",         country="ITA", comp_factor=1.0,  standings_league_id=135),
    LeagueConfig(id=547, name="Supercoppa Italiana",  country="ITA", comp_factor=0.85, standings_league_id=135),
    LeagueConfig(id=66,  name="Coupe de France",      country="FRA", comp_factor=1.0,  standings_league_id=61),
    LeagueConfig(id=526, name="Trophée des Champions",country="FRA", comp_factor=0.80, standings_league_id=61),
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_matchday(round_str: str) -> int | None:
    m = re.search(r"(\d+)$", round_str)
    return int(m.group(1)) if m else None


def _validate_appearance_team(
    fixture_id: int,
    team_id: int,
    home_team_id: int,
    away_team_id: int,
) -> None:
    if team_id not in (home_team_id, away_team_id):
        raise ValueError(
            "Appearance team must match fixture home or away team: "
            f"fixture_id={fixture_id} team_id={team_id}"
        )

# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


class IngestCompetitionUseCase:
    def __init__(
        self,
        provider: FootballDataProviderPort,
        repo: IngestionRepositoryPort,
    ) -> None:
        self._provider = provider
        self._repo = repo

    async def execute(self, league: LeagueConfig, season: int) -> IngestionResult:
        competition_id: int | None = None
        fixtures_processed = 0
        season_str = str(season)

        try:
            # --- Phase 1: Standings ---
            # Cup competitions (Copa del Rey, Supercopa) have no own standings;
            # they borrow the standings of a reference league for team selection
            # and M1 rival-difficulty calculation.
            standings_league_id = league.standings_league_id or league.id
            borrowing_standings = standings_league_id != league.id

            standings = await self._provider.fetch_standings(standings_league_id, season)
            if not standings:
                return IngestionResult(
                    competition=league.name,
                    players_processed=0,
                    fixtures_processed=0,
                    status="completed",
                    error=None,
                )

            competition_id = await self._repo.upsert_competition(
                league.name,
                league.country,
                league.comp_factor,
                league.participant_kind,
            )

            matchday = max((s.played for s in standings), default=0)
            pos_cache: dict[int, int] = {}
            team_id_map: dict[int, int] = {}

            for standing in standings:
                team_db_id = await self._repo.upsert_team(
                    standing.team_external_id, standing.team_name, competition_id
                )
                team_id_map[standing.team_external_id] = team_db_id
                pos_cache[standing.team_external_id] = standing.position

                # Skip standing snapshots for cups: they don't have own standings
                if matchday > 0 and not borrowing_standings:
                    await self._repo.upsert_standing_snapshot(
                        competition_id, team_db_id, season_str,
                        matchday, standing.position, standing.points,
                    )

            # --- Phase 2: Fixtures ---
            # top_n=None means all teams (e.g. WC) → 1 bulk API call instead of N per-team calls
            if league.top_n is None:
                all_fixtures = await self._provider.fetch_league_fixtures(league.id, season)
            else:
                top_teams = sorted(standings, key=lambda s: s.position)[: league.top_n]
                seen_ids: set[int] = set()
                all_fixtures = []
                for team_standing in top_teams:
                    for fx in await self._provider.fetch_team_fixtures(
                        team_standing.team_external_id, league.id, season
                    ):
                        if fx.external_id not in seen_ids:
                            seen_ids.add(fx.external_id)
                            all_fixtures.append(fx)

            # Pre-fetch completed fixture ids to skip Phase 3 for already-processed fixtures
            completed_ids = await self._repo.get_completed_fixture_ids(
                competition_id, season_str
            )

            for fixture in all_fixtures:
                    stage = self._provider.get_stage(fixture.round_str, fixture.league_name)
                    stage_factor = await self._repo.get_stage_factor(competition_id, stage)
                    matchday_num = _parse_matchday(fixture.round_str)

                    # Ensure both teams exist in the DB
                    for ext_id, name in [
                        (fixture.home_team_external_id, fixture.home_team_name),
                        (fixture.away_team_external_id, fixture.away_team_name),
                    ]:
                        if ext_id not in team_id_map:
                            db_id = await self._repo.upsert_team(ext_id, name, competition_id)
                            team_id_map[ext_id] = db_id
                            if ext_id not in pos_cache:
                                pos_cache[ext_id] = 10

                    home_db_id = team_id_map[fixture.home_team_external_id]
                    away_db_id = team_id_map[fixture.away_team_external_id]

                    fixture_db_id = await self._repo.upsert_fixture(
                        fixture.external_id, competition_id,
                        home_db_id, away_db_id,
                        stage, season_str, fixture.played_at, matchday_num,
                        status=fixture.status,
                    )

                    # Skip events/players for fixtures already completed in DB
                    if fixture.external_id in completed_ids:
                        fixtures_processed += 1
                        continue

                    # --- Phase 3: Events and players ---
                    events = await self._provider.fetch_fixture_events(fixture.external_id)
                    await self._repo.save_fixture_events(fixture.external_id, events)
                    score_timeline = ScoreTimeline.build(
                        fixture.home_team_external_id,
                        fixture.away_team_external_id,
                        events,
                    )

                    for proc_team_ext_id in (
                        fixture.home_team_external_id,
                        fixture.away_team_external_id,
                    ):
                        player_stats_list = await self._provider.fetch_fixture_players(
                            fixture.external_id, proc_team_ext_id
                        )

                        rival_ext_id = (
                            fixture.away_team_external_id
                            if proc_team_ext_id == fixture.home_team_external_id
                            else fixture.home_team_external_id
                        )
                        player_team_pos = pos_cache.get(proc_team_ext_id, 10)
                        rival_pos = pos_cache.get(rival_ext_id, 10)
                        is_away = proc_team_ext_id == fixture.away_team_external_id
                        proc_team_db_id = team_id_map[proc_team_ext_id]
                        _validate_appearance_team(
                            fixture_db_id,
                            proc_team_db_id,
                            home_db_id,
                            away_db_id,
                        )

                        for ps in player_stats_list:
                            if ps.minutes < 1:
                                continue
                            if ps.player_external_id <= 0:
                                logger.warning(
                                    "Skipping player %r in fixture %s: invalid external ID %r",
                                    ps.player_name,
                                    fixture.external_id,
                                    ps.player_external_id,
                                )
                                continue

                            position = map_position(ps.player_name, ps.position)
                            update_pos = (
                                ps.player_name in KNOWN_POSITIONS
                                or position != Position.MC
                            )
                            player_db_id = await self._repo.upsert_player(
                                ps.player_external_id, ps.player_name,
                                position,
                                photo_url=ps.photo_url,
                                update_position=update_pos,
                            )

                            await self._repo.upsert_player_stats(
                                player_db_id,
                                fixture_db_id,
                                proc_team_db_id,
                                season_str,
                                {
                                    "goals": ps.goals,
                                    "assists": ps.assists,
                                    "shots_on": ps.shots_on,
                                    "shots_total": ps.shots_total,
                                    "passes_key": ps.passes_key,
                                    "passes_total": ps.passes_total,
                                    "passes_accuracy": ps.passes_accuracy,
                                    "dribbles_won": ps.dribbles_success,
                                    "dribbles_attempts": ps.dribbles_attempts,
                                    "dribbles_past": ps.dribbles_past,
                                    "duels_won": ps.duels_won,
                                    "duels_total": ps.duels_total,
                                    "tackles_won": ps.tackles,
                                    "interceptions": ps.interceptions,
                                    "blocks": ps.blocks,
                                    "fouls_drawn": ps.fouls_drawn,
                                    "fouls_committed": ps.fouls_committed,
                                    "cards_yellow": ps.cards_yellow,
                                    "cards_red": ps.cards_red,
                                    "penalty_won": ps.penalty_won,
                                    "saves": ps.saves,
                                    "goals_conceded": ps.goals_conceded,
                                    "minutes": ps.minutes,
                                    "rating": ps.rating,
                                },
                            )

                            # GK: skip SFA event scoring
                            if position == Position.GK:
                                continue

                            group = position_to_group(position)

                            # Delete stale events for idempotency
                            await self._repo.delete_player_events_for_fixture(
                                player_db_id, fixture_db_id
                            )

                            # Goals
                            player_goals = [
                                e for e in events
                                if e.type == "Goal"
                                and e.detail not in ("Missed Penalty", "Own Goal")
                                and _name_matches(e.player_name, ps.player_name)
                                and e.team_external_id == proc_team_ext_id
                            ]
                            for goal_evt in player_goals:
                                await self._process_event(
                                    evt=goal_evt,
                                    score_timeline=score_timeline,
                                    player_db_id=player_db_id,
                                    fixture_db_id=fixture_db_id,
                                    team_id=proc_team_db_id,
                                    group=group,
                                    player_team_pos=player_team_pos,
                                    rival_pos=rival_pos,
                                    stage_factor=stage_factor,
                                    is_away=is_away,
                                    is_assist=False,
                                )

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
                                await self._process_event(
                                    evt=assist_evt,
                                    score_timeline=score_timeline,
                                    player_db_id=player_db_id,
                                    fixture_db_id=fixture_db_id,
                                    team_id=proc_team_db_id,
                                    group=group,
                                    player_team_pos=player_team_pos,
                                    rival_pos=rival_pos,
                                    stage_factor=stage_factor,
                                    is_away=is_away,
                                    is_assist=True,
                                )

                            # Match stats — stored raw; pts calculated by scoring pipeline v2
                            await self._repo.upsert_player_event(
                                player_id=player_db_id,
                                fixture_id=fixture_db_id,
                                team_id=proc_team_db_id,
                                minute=90,
                                event_type=EventType.STATS,
                                score_before=None,
                                score_diff=None,
                                psxg=None,
                                m1=1.0,
                                m2=1.0,
                                m3=1.0,
                                m4=1.0,
                                mvisit=1.0,
                                pts=0.0,
                                player_team_pos=player_team_pos,
                                rival_team_pos=rival_pos,
                                is_away=is_away,
                            )

                    fixtures_processed += 1

            # --- Phase 4: Log ---
            await self._repo.save_ingestion_log(
                competition_id, season_str,
                IngestionStatus.COMPLETED, None, None,
            )

            return IngestionResult(
                competition=league.name,
                players_processed=0,
                fixtures_processed=fixtures_processed,
                status="completed",
                error=None,
            )

        except Exception as exc:
            logger.exception(
                "Ingestion failed for %s season %s", league.name, season
            )
            if competition_id is not None:
                try:
                    await self._repo.save_ingestion_log(
                        competition_id, season_str,
                        IngestionStatus.FAILED, None, str(exc),
                    )
                except Exception:
                    pass
            return IngestionResult(
                competition=league.name,
                players_processed=0,
                fixtures_processed=fixtures_processed,
                status="failed",
                error=str(exc),
            )

    async def _process_event(
        self,
        *,
        evt: FixtureEventRawDTO,
        score_timeline: ScoreTimeline,
        player_db_id: int,
        fixture_db_id: int,
        team_id: int,
        group: object,
        player_team_pos: int,
        rival_pos: int,
        stage_factor: float,
        is_away: bool,
        is_assist: bool,
    ) -> None:
        minute = evt.minute + evt.extra_minute
        db_minute = max(1, min(120, minute))   # DB constraint: BETWEEN 1 AND 120
        clamped = max(1, min(90, minute))      # M3 clamped to 90 for scoring logic
        is_penalty = evt.detail == "Penalty"
        # Tanda de penales: eventos reportados después del minuto 120
        is_shootout = is_penalty and minute > 120

        transition = score_timeline.transition_for(evt)
        home_b, away_b = transition.home_before, transition.away_before
        score_diff = (away_b - home_b) if is_away else (home_b - away_b)
        score_before_str = f"{home_b}:{away_b}"

        if is_assist:
            is_corner = "corner" in evt.detail.lower()
            psxg: float | None = None
            event_type = EventType.CORNER_ASSIST if is_corner else EventType.ASSIST
        elif is_shootout:
            psxg = None
            event_type = EventType.GOAL_SHOOTOUT
        else:
            psxg = None
            event_type = EventType.GOAL_PENALTY if is_penalty else EventType.GOAL

        # Store raw event; pts calculated by scoring pipeline v2
        await self._repo.upsert_player_event(
            player_db_id, fixture_db_id, team_id,
            db_minute, event_type,
            score_before_str, score_diff, psxg,
            1.0, 1.0, 1.0, 1.0, 1.0,
            0.0,
            player_team_pos=player_team_pos,
            rival_team_pos=rival_pos,
            is_away=is_away,
        )
