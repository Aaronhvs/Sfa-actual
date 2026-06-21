from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import httpx

from sfa.domain.enrichment.birth_date_ports import PlayerBirthDateRawDTO
from sfa.domain.ingestion_ports import (
    FixtureEventRawDTO,
    FixtureRawDTO,
    PlayerStatsRawDTO,
    StandingRawDTO,
)
from sfa.domain.world_cup_ports import (
    WorldCupFixtureDetailDTO,
    WorldCupFixtureDTO,
    WorldCupLineupPlayerDTO,
    WorldCupStandingDTO,
    WorldCupStatisticDTO,
    WorldCupTeamDTO,
    WorldCupTeamLineupDTO,
    WorldCupVenueDTO,
)

logger = logging.getLogger(__name__)

ROUND_TO_STAGE: dict[str, str] = {
    "group stage":     "group",
    "league stage":    "group",
    "round of 32":     "round_of_16",
    "last 16":         "round_of_16",
    "round of 16":     "round_of_16",
    "quarter-finals":  "quarter",
    "quarter finals":  "quarter",
    "semi-finals":     "semi",
    "semi finals":     "semi",
    "3rd place final": "semi",
    "final":           "final",
}


class APIFootballProvider:
    """HTTP adapter for API-Football v3."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._requests_used = 0
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"x-apisports-key": self._api_key},
                timeout=20.0,
            )
        return self._client

    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """HTTP GET with rate limiting, retry, and backoff."""
        client = self._get_client()
        last_exc: Exception | None = None

        for attempt in range(3):
            try:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                data: dict = response.json()
                self._requests_used += 1

                errors = data.get("errors")
                if errors:
                    err_str = str(errors)
                    if "rateLimit" in err_str:
                        logger.warning("Rate limit hit, waiting 65s before retry")
                        await asyncio.sleep(65)
                        continue
                    if "reached the request limit" in err_str.lower():
                        raise RuntimeError(
                            f"API-Football daily request limit reached — "
                            f"resets at midnight UTC. endpoint={endpoint}"
                        )
                    logger.warning("API errors for %s: %s", endpoint, errors)

                return data

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning("Timeout on %s (attempt %d/3)", endpoint, attempt + 1)
                if attempt < 2:
                    await asyncio.sleep(10)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                logger.error("HTTP error on %s: %s", endpoint, exc)
                if attempt < 2:
                    wait = 65 if exc.response.status_code == 429 else 10
                    logger.warning("Waiting %ds before retry (attempt %d/3)", wait, attempt + 1)
                    await asyncio.sleep(wait)

        raise RuntimeError(
            f"Failed to GET /{endpoint} after 3 attempts"
        ) from last_exc

    async def fetch_standings(self, league_id: int, season: int) -> list[StandingRawDTO]:
        data = await self._get("standings", {"league": league_id, "season": season})
        try:
            all_groups = data["response"][0]["league"]["standings"]
        except (IndexError, KeyError, TypeError):
            logger.warning("No standings data for league %d season %d", league_id, season)
            return []

        result: list[StandingRawDTO] = []
        for group in all_groups:
            for entry in group:
                result.append(
                    StandingRawDTO(
                        team_external_id=entry["team"]["id"],
                        team_name=entry["team"]["name"],
                        position=entry["rank"],
                        points=entry["points"],
                        played=entry["all"]["played"],
                    )
                )
        return result

    async def fetch_world_cup_fixtures(
        self,
        league_id: int,
        season: int,
    ) -> list[WorldCupFixtureDTO]:
        data = await self._get("fixtures", {"league": league_id, "season": season})
        fixtures: list[WorldCupFixtureDTO] = []

        for item in data.get("response", []):
            try:
                fixture = item["fixture"]
                league = item["league"]
                teams = item["teams"]
                goals = item["goals"]
                round_name = league.get("round") or "Mundial 2026"
                fixtures.append(
                    WorldCupFixtureDTO(
                        external_id=fixture["id"],
                        stage=round_name,
                        matchday=self._world_cup_matchday(round_name),
                        played_at=datetime.fromisoformat(fixture["date"]),
                        status=fixture["status"].get("short") or "NS",
                        status_label=fixture["status"].get("long") or "Programado",
                        elapsed=fixture["status"].get("elapsed"),
                        home_team=WorldCupTeamDTO(
                            external_id=teams["home"]["id"],
                            name=teams["home"]["name"],
                        ),
                        away_team=WorldCupTeamDTO(
                            external_id=teams["away"]["id"],
                            name=teams["away"]["name"],
                        ),
                        home_goals=goals.get("home"),
                        away_goals=goals.get("away"),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "[APIFootballProvider] Skipping malformed World Cup fixture: %s",
                    exc,
                )

        return sorted(fixtures, key=lambda item: item.played_at)

    async def fetch_world_cup_standings(
        self,
        league_id: int,
        season: int,
    ) -> list[WorldCupStandingDTO]:
        data = await self._get("standings", {"league": league_id, "season": season})
        try:
            groups = data["response"][0]["league"]["standings"]
        except (IndexError, KeyError, TypeError):
            logger.warning(
                "[APIFootballProvider] No World Cup standings for league=%d season=%d",
                league_id,
                season,
            )
            return []

        standings: list[WorldCupStandingDTO] = []
        for group in groups:
            for entry in group:
                group_name = entry.get("group") or ""
                if group_name == "Group Stage":
                    continue
                try:
                    all_stats = entry.get("all") or {}
                    goals = all_stats.get("goals") or {}
                    standings.append(
                        WorldCupStandingDTO(
                            group=group_name,
                            position=entry["rank"],
                            team=WorldCupTeamDTO(
                                external_id=entry["team"]["id"],
                                name=entry["team"]["name"],
                            ),
                            played=all_stats.get("played") or 0,
                            won=all_stats.get("win") or 0,
                            drawn=all_stats.get("draw") or 0,
                            lost=all_stats.get("lose") or 0,
                            goals_for=goals.get("for") or 0,
                            goals_against=goals.get("against") or 0,
                            goal_difference=entry.get("goalsDiff") or 0,
                            points=entry.get("points") or 0,
                            form=entry.get("form"),
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    logger.warning(
                        "[APIFootballProvider] Skipping malformed World Cup standing: %s",
                        exc,
                    )

        return standings

    async def fetch_world_cup_fixture_detail(
        self,
        fixture_id: int,
    ) -> WorldCupFixtureDetailDTO | None:
        fixture_data, lineup_data, statistics_data = await asyncio.gather(
            self._get("fixtures", {"id": fixture_id}),
            self._get("fixtures/lineups", {"fixture": fixture_id}),
            self._get("fixtures/statistics", {"fixture": fixture_id}),
        )
        fixture_items = fixture_data.get("response", [])
        if not fixture_items:
            return None

        item = fixture_items[0]
        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        teams = item.get("teams") or {}
        goals = item.get("goals") or {}
        status = fixture.get("status") or {}
        venue = fixture.get("venue") or {}
        round_name = league.get("round") or "Mundial 2026"

        home_team = self._world_cup_team(teams.get("home"))
        away_team = self._world_cup_team(teams.get("away"))
        if home_team is None or away_team is None:
            logger.warning(
                "[APIFootballProvider] Missing teams for fixture=%d",
                fixture_id,
            )
            return None

        fixture_dto = WorldCupFixtureDTO(
            external_id=fixture["id"],
            stage=round_name,
            matchday=self._world_cup_matchday(round_name),
            played_at=datetime.fromisoformat(fixture["date"]),
            status=status.get("short") or "NS",
            status_label=status.get("long") or "Programado",
            elapsed=status.get("elapsed"),
            home_team=home_team,
            away_team=away_team,
            home_goals=goals.get("home"),
            away_goals=goals.get("away"),
        )

        lineups = [
            lineup
            for raw_lineup in lineup_data.get("response", [])
            if (lineup := self._world_cup_lineup(raw_lineup)) is not None
        ]
        statistics = self._world_cup_statistics(
            statistics_data.get("response", []),
            home_team.external_id,
            away_team.external_id,
        )
        return WorldCupFixtureDetailDTO(
            fixture=fixture_dto,
            venue=WorldCupVenueDTO(
                name=venue.get("name"),
                city=venue.get("city"),
            ),
            referee=fixture.get("referee"),
            lineups=lineups,
            statistics=statistics,
            events=[],
        )

    @staticmethod
    def _world_cup_team(data: dict | None) -> WorldCupTeamDTO | None:
        if not data or not isinstance(data.get("id"), int):
            return None
        return WorldCupTeamDTO(
            external_id=data["id"],
            name=data.get("name") or "",
        )

    @staticmethod
    def _world_cup_lineup_player(data: dict) -> WorldCupLineupPlayerDTO:
        player = data.get("player") or {}
        return WorldCupLineupPlayerDTO(
            external_id=player.get("id"),
            name=player.get("name") or "",
            number=player.get("number"),
            position=player.get("pos"),
            grid=player.get("grid"),
        )

    def _world_cup_lineup(
        self,
        data: dict,
    ) -> WorldCupTeamLineupDTO | None:
        team = self._world_cup_team(data.get("team"))
        if team is None:
            return None
        coach = data.get("coach") or {}
        return WorldCupTeamLineupDTO(
            team=team,
            formation=data.get("formation"),
            coach_name=coach.get("name"),
            coach_photo=coach.get("photo"),
            start_xi=[
                self._world_cup_lineup_player(player)
                for player in data.get("startXI", [])
            ],
            substitutes=[
                self._world_cup_lineup_player(player)
                for player in data.get("substitutes", [])
            ],
        )

    @classmethod
    def _world_cup_statistics(
        cls,
        team_statistics: list[dict],
        home_team_id: int,
        away_team_id: int,
    ) -> list[WorldCupStatisticDTO]:
        values_by_team: dict[int, dict[str, object]] = {}
        labels: list[str] = []
        for entry in team_statistics:
            team_id = (entry.get("team") or {}).get("id")
            if not isinstance(team_id, int):
                continue
            values: dict[str, object] = {}
            for statistic in entry.get("statistics", []):
                label = statistic.get("type")
                if not label:
                    continue
                if label not in labels:
                    labels.append(label)
                values[label] = statistic.get("value")
            values_by_team[team_id] = values

        home_values = values_by_team.get(home_team_id, {})
        away_values = values_by_team.get(away_team_id, {})
        return [
            WorldCupStatisticDTO(
                label=label,
                home_value=cls._stat_display(home_values.get(label)),
                away_value=cls._stat_display(away_values.get(label)),
                home_numeric=cls._stat_numeric(home_values.get(label)),
                away_numeric=cls._stat_numeric(away_values.get(label)),
            )
            for label in labels
        ]

    @staticmethod
    def _stat_display(value: object) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _stat_numeric(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).rstrip("%"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _world_cup_matchday(round_name: str) -> int | None:
        marker = "Group Stage - "
        if not round_name.startswith(marker):
            return None
        try:
            return int(round_name.removeprefix(marker))
        except ValueError:
            return None

    async def fetch_team_fixtures(
        self, team_id: int, league_id: int, season: int,
    ) -> list[FixtureRawDTO]:
        data = await self._get(
            "fixtures",
            # FT = full time, AET = after extra time, PEN = after penalties
            {"team": team_id, "league": league_id, "season": season, "status": "FT-AET-PEN"},
        )
        result: list[FixtureRawDTO] = []
        for f in data.get("response", []):
            try:
                played_at = datetime.fromisoformat(f["fixture"]["date"])
                result.append(
                    FixtureRawDTO(
                        external_id=f["fixture"]["id"],
                        home_team_external_id=f["teams"]["home"]["id"],
                        away_team_external_id=f["teams"]["away"]["id"],
                        home_team_name=f["teams"]["home"]["name"],
                        away_team_name=f["teams"]["away"]["name"],
                        round_str=f["league"]["round"],
                        league_name=f["league"]["name"],
                        played_at=played_at,
                        home_goals=f["goals"]["home"] or 0,
                        away_goals=f["goals"]["away"] or 0,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping malformed fixture: %s", exc)
        return result

    async def fetch_league_fixtures(
        self, league_id: int, season: int,
    ) -> list[FixtureRawDTO]:
        data = await self._get("fixtures", {"league": league_id, "season": season})
        result: list[FixtureRawDTO] = []
        for f in data.get("response", []):
            try:
                played_at = datetime.fromisoformat(f["fixture"]["date"])
                result.append(
                    FixtureRawDTO(
                        external_id=f["fixture"]["id"],
                        home_team_external_id=f["teams"]["home"]["id"],
                        away_team_external_id=f["teams"]["away"]["id"],
                        home_team_name=f["teams"]["home"]["name"],
                        away_team_name=f["teams"]["away"]["name"],
                        round_str=f["league"]["round"],
                        league_name=f["league"]["name"],
                        played_at=played_at,
                        home_goals=f["goals"].get("home") or 0,
                        away_goals=f["goals"].get("away") or 0,
                        status=f["fixture"]["status"].get("short") or "NS",
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("[fetch_league_fixtures] Skipping malformed fixture: %s", exc)
        return result

    async def fetch_fixture_events(self, fixture_id: int) -> list[FixtureEventRawDTO]:
        data = await self._get("fixtures/events", {"fixture": fixture_id})
        result: list[FixtureEventRawDTO] = []
        for source_sequence, e in enumerate(data.get("response", [])):
            try:
                result.append(
                    FixtureEventRawDTO(
                        type=e.get("type") or "",
                        detail=e.get("detail") or "",
                        player_name=e["player"].get("name") or "",
                        assist_name=e["assist"].get("name"),
                        team_external_id=e["team"]["id"],
                        minute=e["time"]["elapsed"] or 0,
                        extra_minute=e["time"]["extra"] or 0,
                        source_sequence=source_sequence,
                    )
                )
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed event: %s", exc)
        return result

    async def fetch_fixture_players(
        self, fixture_id: int, team_id: int,
    ) -> list[PlayerStatsRawDTO]:
        data = await self._get("fixtures/players", {"fixture": fixture_id})
        result: list[PlayerStatsRawDTO] = []

        for team_data in data.get("response", []):
            if team_data["team"]["id"] != team_id:
                continue
            for p in team_data.get("players", []):
                try:
                    player_data = p.get("player") or {}
                    player_external_id = player_data.get("id")
                    if not isinstance(player_external_id, int) or player_external_id <= 0:
                        logger.warning(
                            "Skipping player stats with invalid external ID: %r",
                            player_external_id,
                        )
                        continue
                    stats = p["statistics"][0] if p.get("statistics") else {}
                    games = stats.get("games") or {}
                    goals = stats.get("goals") or {}
                    shots = stats.get("shots") or {}
                    passes = stats.get("passes") or {}
                    dribbles = stats.get("dribbles") or {}
                    duels = stats.get("duels") or {}
                    tackles = stats.get("tackles") or {}
                    fouls = stats.get("fouls") or {}
                    cards = stats.get("cards") or {}
                    penalty = stats.get("penalty") or {}

                    raw_rating = games.get("rating")
                    try:
                        rating = float(raw_rating) if raw_rating is not None else None
                    except (TypeError, ValueError):
                        rating = None

                    raw_accuracy = passes.get("accuracy")
                    try:
                        passes_accuracy = min(100, max(0, int(raw_accuracy))) if raw_accuracy is not None else 80
                    except (TypeError, ValueError):
                        passes_accuracy = 80

                    result.append(
                        PlayerStatsRawDTO(
                            player_external_id=player_external_id,
                            player_name=player_data["name"],
                            photo_url=player_data.get("photo") or None,
                            position=games.get("position") or "Midfielder",
                            minutes=games.get("minutes") or 0,
                            goals=goals.get("total") or 0,
                            assists=goals.get("assists") or 0,
                            shots_on=shots.get("on") or 0,
                            shots_total=shots.get("total") or 0,
                            passes_key=passes.get("key") or 0,
                            passes_total=passes.get("total") or 0,
                            passes_accuracy=passes_accuracy,
                            dribbles_success=dribbles.get("success") or 0,
                            dribbles_attempts=dribbles.get("attempts") or 0,
                            dribbles_past=dribbles.get("past") or 0,
                            duels_won=duels.get("won") or 0,
                            duels_total=duels.get("total") or 0,
                            tackles=tackles.get("total") or 0,
                            interceptions=tackles.get("interceptions") or 0,
                            blocks=tackles.get("blocks") or 0,
                            fouls_drawn=fouls.get("drawn") or 0,
                            fouls_committed=fouls.get("committed") or 0,
                            cards_yellow=cards.get("yellow") or 0,
                            cards_red=cards.get("red") or 0,
                            penalty_won=penalty.get("won") or 0,
                            saves=goals.get("saves") or 0,
                            goals_conceded=goals.get("conceded") or 0,
                            rating=rating,
                        )
                    )
                except (KeyError, TypeError, IndexError) as exc:
                    logger.warning("Skipping malformed player stats: %s", exc)
        return result

    async def fetch_all_fixture_players(
        self, fixture_external_id: int,
    ) -> list[PlayerStatsRawDTO]:
        """Fetch player stats for all teams in a fixture (no team filter)."""
        data = await self._get("fixtures/players", {"fixture": fixture_external_id})
        result: list[PlayerStatsRawDTO] = []

        for team_data in data.get("response", []):
            for p in team_data.get("players", []):
                try:
                    player_data = p.get("player") or {}
                    player_external_id = player_data.get("id")
                    if not isinstance(player_external_id, int) or player_external_id <= 0:
                        logger.warning(
                            "Skipping player stats with invalid external ID: %r",
                            player_external_id,
                        )
                        continue
                    stats = p["statistics"][0] if p.get("statistics") else {}
                    games = stats.get("games") or {}
                    goals = stats.get("goals") or {}
                    shots = stats.get("shots") or {}
                    passes = stats.get("passes") or {}
                    dribbles = stats.get("dribbles") or {}
                    duels = stats.get("duels") or {}
                    tackles = stats.get("tackles") or {}
                    fouls = stats.get("fouls") or {}
                    cards = stats.get("cards") or {}
                    penalty = stats.get("penalty") or {}

                    raw_rating = games.get("rating")
                    try:
                        rating = float(raw_rating) if raw_rating is not None else None
                    except (TypeError, ValueError):
                        rating = None

                    raw_accuracy = passes.get("accuracy")
                    try:
                        passes_accuracy = min(100, max(0, int(raw_accuracy))) if raw_accuracy is not None else 80
                    except (TypeError, ValueError):
                        passes_accuracy = 80

                    result.append(
                        PlayerStatsRawDTO(
                            player_external_id=player_external_id,
                            player_name=player_data["name"],
                            photo_url=player_data.get("photo") or None,
                            position=games.get("position") or "Midfielder",
                            minutes=games.get("minutes") or 0,
                            goals=goals.get("total") or 0,
                            assists=goals.get("assists") or 0,
                            shots_on=shots.get("on") or 0,
                            shots_total=shots.get("total") or 0,
                            passes_key=passes.get("key") or 0,
                            passes_total=passes.get("total") or 0,
                            passes_accuracy=passes_accuracy,
                            dribbles_success=dribbles.get("success") or 0,
                            dribbles_attempts=dribbles.get("attempts") or 0,
                            dribbles_past=dribbles.get("past") or 0,
                            duels_won=duels.get("won") or 0,
                            duels_total=duels.get("total") or 0,
                            tackles=tackles.get("total") or 0,
                            interceptions=tackles.get("interceptions") or 0,
                            blocks=tackles.get("blocks") or 0,
                            fouls_drawn=fouls.get("drawn") or 0,
                            fouls_committed=fouls.get("committed") or 0,
                            cards_yellow=cards.get("yellow") or 0,
                            cards_red=cards.get("red") or 0,
                            penalty_won=penalty.get("won") or 0,
                            saves=goals.get("saves") or 0,
                            goals_conceded=goals.get("conceded") or 0,
                            rating=rating,
                        )
                    )
                except (KeyError, TypeError, IndexError) as exc:
                    logger.warning("[fetch_all_fixture_players] Skipping malformed player: %s", exc)
        return result

    async def fetch_squad_birth_dates(
        self,
        team_id: int,
        season: int,
    ) -> list[PlayerBirthDateRawDTO]:
        """Fetch birth dates for all players in a team squad (1 API request)."""
        data = await self._get("players", {"team": team_id, "season": season})
        result: list[PlayerBirthDateRawDTO] = []
        for entry in data.get("response", []):
            dto = self._parse_player_birth_date(entry)
            if dto is not None:
                result.append(dto)
        return result

    async def fetch_player_birth_date(
        self,
        player_id: int,
        season: int,
    ) -> PlayerBirthDateRawDTO | None:
        """Fetch birth date for one player when squad lookup did not include them."""
        data = await self._get("players", {"id": player_id, "season": season})
        for entry in data.get("response", []):
            dto = self._parse_player_birth_date(entry)
            if dto is not None:
                return dto
        return None

    def _parse_player_birth_date(self, entry: dict) -> PlayerBirthDateRawDTO | None:
        player = entry.get("player") or {}
        external_id = player.get("id")
        if not isinstance(external_id, int) or external_id <= 0:
            return None

        raw_date = (player.get("birth") or {}).get("date")
        birth_date: date | None = None
        if raw_date:
            try:
                birth_date = date.fromisoformat(raw_date)
            except (ValueError, TypeError):
                logger.warning(
                    "[APIFootballProvider] Invalid birth.date=%r for player_id=%d",
                    raw_date,
                    external_id,
                )
        return PlayerBirthDateRawDTO(external_id=external_id, birth_date=birth_date)

    def get_stage(self, round_str: str, league_name: str) -> str:
        """Map API-Football round string → SFA stage."""
        key = round_str.lower().strip()
        for pattern, stage in ROUND_TO_STAGE.items():
            if pattern in key:
                return stage
        return "regular"

    @property
    def requests_used(self) -> int:
        return self._requests_used
