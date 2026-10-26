"""Read model for the best single-match performance of each competition round."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping, Protocol, Sequence, runtime_checkable

from sfa.domain.ports import TournamentCompetitionDTO, TournamentFixtureDTO, TournamentTeamDTO
from sfa.domain.season_scope import AwardPeriodScope

POLICY_VERSION = "matchday-mvp-v1"
FINAL_STATUSES = frozenset(("FT", "AET", "PEN"))
FEATURED_NAMES = ("champions league", "la liga", "premier league", "serie a", "bundesliga",
                  "ligue 1", "europa league", "conference league")
CONTINENTAL = frozenset((FEATURED_NAMES[0], FEATURED_NAMES[6], FEATURED_NAMES[7]))
LEAGUES = frozenset(FEATURED_NAMES[1:6])
SINGLE_CUPS = frozenset(("fa cup", "efl cup", "dfb-pokal", "coppa italia", "copa del rey",
                         "supercopa de españa", "super cup", "community shield", "dfl-supercup",
                         "trophée des champions", "coupe de france", "supercoppa italiana"))
STAGES = {"round_of_128": (10, "Primera ronda"), "round_of_64": (11, "Segunda ronda"),
          "round_of_32": (12, "Dieciseisavos"), "play_offs": (13, "Play-offs"),
          "round_of_16": (14, "Octavos"), "quarter": (15, "Cuartos"), "semi": (16, "Semifinales"),
          "final": (17, "Final")}


@dataclass(frozen=True)
class MvpRound:
    key: str
    label: str
    matchday: int | None
    order: tuple[int, int]
    fixtures: tuple[TournamentFixtureDTO, ...]
    knockout: bool = False


@dataclass(frozen=True)
class MvpPerformance:
    player_id: int
    fixture_id: int
    name: str
    photo_url: str | None
    team_id: int
    points: Decimal
    goals: int
    assists: int
    decisive_score_diff: int | None = None
    rival_strength: float | None = None


@dataclass(frozen=True)
class MvpPlayer:
    id: int
    name: str
    team: str
    position: str
    photo_url: str | None


@dataclass(frozen=True)
class MvpFixture:
    external_id: int
    played_at: datetime
    home_team: TournamentTeamDTO
    away_team: TournamentTeamDTO
    home_goals: int | None
    away_goals: int | None
    player_side: str


@dataclass(frozen=True)
class MatchdayMvp:
    round_key: str
    round_label: str
    matchday: int | None
    complete: bool
    pending_fixtures: int
    player: MvpPlayer
    sfa_pts: float
    goals: int
    assists: int
    reasons: tuple[str, ...]
    fixture: MvpFixture


def competition_key(name: str) -> str:
    return name.strip().casefold().removeprefix("uefa ")


def group_rounds(competition_name: str, fixtures: Sequence[TournamentFixtureDTO]) -> tuple[MvpRound, ...]:
    """Infer two legs only from a complete, coherent local home/away tie."""
    name = competition_key(competition_name)
    groups: dict[tuple[str, str, int | None, tuple[int, int], bool], list] = defaultdict(list)
    knockout: dict[str, list] = defaultdict(list)
    for fixture in fixtures:
        stage = fixture.stage.strip().lower().replace(" ", "_").replace("-", "_")
        league_stage = (name in LEAGUES and stage in {"regular", "regular_season"}) or (
            name in CONTINENTAL and stage in {"group", "league_stage"}
        )
        if league_stage and fixture.matchday is not None and 1 <= fixture.matchday <= 60:
            day = fixture.matchday
            groups[(f"matchday-{day}", f"Jornada {day}", day, (0, day), False)].append(fixture)
        elif stage in STAGES or re.fullmatch(r".+_leg_[12]", stage):
            knockout[stage].append(fixture)
    for raw_stage, stage_fixtures in knockout.items():
        explicit = re.fullmatch(r"(.+)_leg_([12])", raw_stage)
        stage = explicit[1] if explicit else raw_stage
        if stage not in STAGES:
            continue
        order, label = STAGES[stage]
        if stage == "final" and len(stage_fixtures) != 1:
            continue  # Some historical imports mislabeled many early cup games as finals.
        two_legs = stage != "final" and (name in CONTINENTAL or (
            name in {"copa del rey", "coppa italia", "efl cup"} and stage == "semi"
        ))
        if explicit and two_legs:
            legs = {int(explicit[2]): stage_fixtures}
        elif two_legs:
            pairs: dict[tuple[int, int], list] = defaultdict(list)
            for fixture in stage_fixtures:
                pairs[tuple(sorted((fixture.home_team.id, fixture.away_team.id)))].append(fixture)
            legs = {1: [], 2: []}
            for pair in pairs.values():
                if len(pair) != 2:
                    continue
                first, second = sorted(pair, key=lambda item: (item.played_at, item.external_id))
                if (first.played_at == second.played_at or first.home_team.id != second.away_team.id
                        or first.away_team.id != second.home_team.id or first.id == second.id):
                    continue
                legs[1].append(first)
                legs[2].append(second)
        elif name in SINGLE_CUPS or (stage == "final" and name in CONTINENTAL):
            legs = {0: stage_fixtures}
        else:
            continue
        for leg, members in legs.items():
            if members:
                suffix = f"leg-{leg}" if leg else "single"
                title = f"{label} · {'ida' if leg == 1 else 'vuelta'}" if leg else label
                groups[(f"{stage}-{suffix}", title, None, (order, leg), True)].extend(members)
    return tuple(sorted((MvpRound(key, label, day, order, tuple(members), ko)
                         for (key, label, day, order, ko), members in groups.items()), key=lambda item: item.order))


def select_mvps(rounds: Sequence[MvpRound], performances: Sequence[MvpPerformance],
                positions: Mapping[int, str | None]) -> tuple[MatchdayMvp, ...]:
    by_fixture: dict[int, list[MvpPerformance]] = defaultdict(list)
    for performance in performances:
        by_fixture[performance.fixture_id].append(performance)
    items = []
    for group in rounds:
        fixtures = {fixture.id: fixture for fixture in group.fixtures}
        candidates = [p for fixture in group.fixtures if fixture.status in FINAL_STATUSES
                      for p in by_fixture[fixture.id]
                      if p.team_id in (fixture.home_team.id, fixture.away_team.id)]
        if not candidates:
            continue
        winner = min(candidates, key=lambda p: (-p.points, -(p.goals + p.assists), p.player_id,
                                                fixtures[p.fixture_id].external_id))
        fixture = fixtures[winner.fixture_id]
        away = winner.team_id == fixture.away_team.id
        team = fixture.away_team if away else fixture.home_team
        pending = sum(f.status not in FINAL_STATUSES for f in group.fixtures)
        reasons = []
        if winner.rival_strength is not None and winner.rival_strength >= 50:
            reasons.append("big_rival")
        if winner.decisive_score_diff is not None:
            if winner.decisive_score_diff < 0:
                reasons.append("behind")
            elif winner.decisive_score_diff == 0:
                reasons.append("level")
        if away:
            reasons.append("away")
        if group.knockout:
            reasons.append("knockout")
        items.append(MatchdayMvp(
            group.key, group.label, group.matchday, pending == 0, pending,
            MvpPlayer(winner.player_id, winner.name, team.name, positions.get(winner.player_id) or "",
                      winner.photo_url), float(winner.points), winner.goals, winner.assists, tuple(reasons),
            MvpFixture(fixture.external_id, fixture.played_at, fixture.home_team, fixture.away_team,
                       fixture.home_goals, fixture.away_goals, "away" if away else "home"),
        ))
    return tuple(items)


@runtime_checkable
class MatchdayMvpRepositoryProtocol(Protocol):
    async def competition_exists(self, competition_id: int) -> bool: ...
    async def get_fixtures(self, competition_id: int, season: str) -> Sequence[TournamentFixtureDTO]: ...
    async def get_performances(self, competition_id: int, season: str,
                               rules_version_id: int) -> Sequence[MvpPerformance]: ...
    async def get_positions(self, scope: AwardPeriodScope, competition_id: int) -> Mapping[int, str | None]: ...
    async def get_data_stamp(self, scope: AwardPeriodScope, competition_id: int, season: str,
                             rules_version_id: int) -> str: ...


@runtime_checkable
class MatchdayMvpCacheProtocol(Protocol):
    async def read(self, key: str) -> tuple[MatchdayMvp, ...] | None: ...
    async def write(self, key: str, items: tuple[MatchdayMvp, ...]) -> None: ...


@runtime_checkable
class CompetitionPositionsProtocol(Protocol):
    async def get_competition_positions(
        self, scope: AwardPeriodScope, competition_id: int | None = None,
    ) -> Mapping[tuple[int, str, int], str | None]: ...


@runtime_checkable
class TournamentMvpReaderProtocol(Protocol):
    async def get_items(self, competition: TournamentCompetitionDTO, season: str) -> tuple[MatchdayMvp, ...]: ...
