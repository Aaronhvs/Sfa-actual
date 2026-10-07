from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from sfa.domain.team_ranking_ports import (
    RankedTeamDTO,
    TeamRankingDataDTO,
    TeamRankingFeaturedPlayerDTO,
    TeamRankingPlayerDTO,
    TeamRankingRepositoryProtocol,
)

RECENT_MATCHES = 10
SHRINKAGE_MINUTES = 450
ELO_WEIGHT = 0.8
SQUAD_WEIGHT = 0.2


@dataclass(frozen=True)
class TeamRankingModel:
    version: str
    label: str
    descriptive_only: bool
    experimental: bool
    feeds_m1: bool
    elo_weight: float
    squad_weight: float
    recent_matches: int
    shrinkage_minutes: int
    rules_version_id: int | None
    population_teams: int
    participant_kind: str
    as_of: datetime
    data_cutoff: datetime | None
    normalization: str
    sources: tuple[str, ...]
    exclusions: tuple[str, ...]
    attribution: str
    fallback: str
    caveats: tuple[str, ...]


@dataclass(frozen=True)
class TeamRankingPagination:
    page: int
    limit: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


@dataclass(frozen=True)
class GetTeamRankingResult:
    season: str
    scope: str | None
    total: int
    pagination: TeamRankingPagination
    model: TeamRankingModel
    ranking: tuple[RankedTeamDTO, ...]


def _prior_season(season: str) -> str:
    if not re.fullmatch(r"(?:19|20)\d{2}(?:-\d{2})?", season):
        raise ValueError("season must be YYYY or YYYY-YY")
    year = int(season[:4])
    if "-" in season:
        if int(season[-2:]) != (year + 1) % 100:
            raise ValueError("season end year must follow start year")
        return f"{year - 1}-{year % 100:02d}"
    return str(year - 1)


def _percentiles(values: dict[object, float]) -> dict[object, float]:
    groups: dict[float, list[object]] = defaultdict(list)
    for key, value in values.items():
        groups[value].append(key)
    result = {}
    lower = 0
    for value in sorted(groups):
        keys = groups[value]
        percentile = 50.0 if len(values) == 1 else 100 * (lower + (len(keys) - 1) / 2) / (len(values) - 1)
        result.update((key, percentile) for key in keys)
        lower += len(keys)
    return result


@runtime_checkable
class GetTeamRankingUseCaseProtocol(Protocol):
    async def execute(
        self, season: str | None = None, scope: str | None = None,
        participant_kind: str = "club", competition_id: int | None = None,
        name: str | None = None, page: int = 1, limit: int = 10,
    ) -> GetTeamRankingResult: ...


class GetTeamRankingUseCase(GetTeamRankingUseCaseProtocol):
    def __init__(self, repository: TeamRankingRepositoryProtocol) -> None:
        self._repository = repository

    async def execute(
        self, season: str | None = None, scope: str | None = None,
        participant_kind: str = "club", competition_id: int | None = None,
        name: str | None = None, page: int = 1, limit: int = 10,
    ) -> GetTeamRankingResult:
        if season is not None and scope is not None:
            raise ValueError("scope and season are mutually exclusive")
        if participant_kind not in ("club", "national", "national_team"):
            raise ValueError("participant_kind must be club, national or national_team")
        participant_kind = "national_team" if participant_kind == "national" else participant_kind
        if page < 1 or not 1 <= limit <= 50 or (competition_id is not None and competition_id < 1):
            raise ValueError("invalid pagination or competition_id")
        if scope is not None:
            if not scope.startswith("season-"):
                raise ValueError("only season-YYYY or season-YYYY-YY scopes are supported")
            season = scope.removeprefix("season-")
        season = season if season is not None else await self._repository.latest_season(participant_kind)
        as_of = datetime.now(timezone.utc)
        data = TeamRankingDataDTO()
        if season is not None:
            prior = _prior_season(season)
            data = await self._repository.get_ranking_data(season, prior, participant_kind, as_of, RECENT_MATCHES)
        else:
            prior = ""

        # Normalize all teams before search/competition filters; historical seasons have separate cohorts.
        cohort_totals: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(dict)
        appearances: dict[tuple[int, str], list[TeamRankingPlayerDTO]] = defaultdict(list)
        for player in data.players:
            appearances[player.team_id, player.season].append(player)
            if player.individual_points is not None and player.scored_minutes > 0:
                totals = cohort_totals[player.season, player.position].setdefault(player.player_id, [0.0, 0.0])
                totals[0] += player.individual_points
                totals[1] += player.scored_minutes
        cohorts = {
            cohort: {player_id: points * 90 / minutes for player_id, (points, minutes) in totals.items()}
            for cohort, totals in cohort_totals.items()
        }
        normalized = {cohort: _percentiles(values) for cohort, values in cohorts.items()}
        elos_by_team_season = {(e.team_id, e.season): e for e in data.elos}
        selected_elos = {}
        for team in data.teams:
            for candidate_season in (season, prior):
                elo = elos_by_team_season.get((team.id, candidate_season))
                if elo is not None:
                    selected_elos[team.id] = elo
                    break
        elo_percentiles = _percentiles({key: elo.elo_raw for key, elo in selected_elos.items()})
        items = []
        for team in data.teams:
            current = appearances.get((team.id, season), [])
            featured_candidates = [p for p in current if p.individual_points is not None
                                   and p.scored_minutes > 0 and p.scored_appearances > 0]
            featured = min(featured_candidates, key=lambda p: (-p.individual_points, p.player_id), default=None)
            previous = appearances.get((team.id, prior), [])
            has_current_scores = any(p.individual_points is not None and p.scored_minutes > 0 for p in current)
            players = current if has_current_scores else previous
            if not players:
                players = current
            scored = [p for p in players if p.individual_points is not None and p.scored_minutes > 0]
            minutes = sum(p.scored_minutes for p in scored)
            squad_score = None
            if minutes:
                weighted = 0.0
                for p in scored:
                    percentile = normalized[p.season, p.position][p.player_id]
                    shrunk = 50 + (percentile - 50) * p.scored_minutes / (p.scored_minutes + SHRINKAGE_MINUTES)
                    weighted += shrunk * p.scored_minutes
                squad_score = weighted / minutes
            elo = selected_elos.get(team.id)
            elo_score = elo_percentiles.get(team.id)
            ew = ELO_WEIGHT if elo_score is not None else 0.0
            sw = SQUAD_WEIGHT if squad_score is not None else 0.0
            weight = ew + sw
            score = ((elo_score or 0) * ew + (squad_score or 0) * sw) / weight if weight else None
            observed = sum(p.observed_appearances for p in players)
            covered = sum(p.scored_appearances for p in scored)
            item = RankedTeamDTO(
                rank=0, id=team.id, name=team.name,
                team_logo_url=f"https://media.api-sports.io/football/teams/{team.external_id}.png"
                if team.external_id is not None else None,
                competition_id=team.competition_id, competition=team.competition,
                score=score, elo_raw=elo.elo_raw if elo else None, elo_score=elo_score, squad_score=squad_score,
                effective_elo_weight=ew / weight if weight else 0.0,
                effective_squad_weight=sw / weight if weight else 0.0,
                elo_season=elo.season if elo else None, elo_source=elo.source if elo else None,
                squad_season=players[0].season if players else None,
                observed_players=len(players), scored_players=len(scored),
                observed_appearances=observed, scored_appearances=covered,
                coverage=covered / observed if observed else None,
                squad_data_cutoff=max((p.data_cutoff for p in scored if p.data_cutoff is not None), default=None),
                featured_player=TeamRankingFeaturedPlayerDTO(
                    id=featured.player_id, name=featured.name, photo_url=featured.photo_url,
                    individual_points=featured.individual_points, appearances=featured.scored_appearances,
                    season=featured.season,
                ) if featured is not None else None,
            )
            if competition_id is not None and competition_id not in team.competition_ids:
                continue
            if name and name.strip().casefold() not in team.name.casefold():
                continue
            items.append(item)
        items.sort(key=lambda item: (item.score is None, -(item.score or 0), item.id))
        total = len(items)
        pages = (total + limit - 1) // limit
        ranking = tuple(
            replace(item, rank=index + 1,
                    score=round(item.score, 4) if item.score is not None else None,
                    elo_score=round(item.elo_score, 4) if item.elo_score is not None else None,
                    squad_score=round(item.squad_score, 4) if item.squad_score is not None else None)
            for index, item in enumerate(items) if (page - 1) * limit <= index < page * limit
        )
        if ranking and season is not None:
            recent_results = await self._repository.get_recent_results(
                tuple(item.id for item in ranking), season, participant_kind, as_of,
            )
            ranking = tuple(replace(item, recent_results=recent_results.get(item.id, ())) for item in ranking)
        return GetTeamRankingResult(
            season=season or "", scope=f"season-{season}" if season else None, total=total,
            pagination=TeamRankingPagination(page, limit, total, pages, page < pages, page > 1 and pages > 0),
            model=TeamRankingModel(
                version="team-observed-merit-v1", label="Descriptive ELO + observed individual SFA merit",
                descriptive_only=True, experimental=True, feeds_m1=False,
                elo_weight=ELO_WEIGHT, squad_weight=SQUAD_WEIGHT,
                recent_matches=RECENT_MATCHES, shrinkage_minutes=SHRINKAGE_MINUTES,
                rules_version_id=data.rules_version_id, population_teams=len(data.teams),
                participant_kind=participant_kind, as_of=as_of,
                data_cutoff=max((p.data_cutoff for p in data.players if p.data_cutoff is not None), default=None),
                normalization="Midrank percentiles per catalog position and physical season of individual SFA/90; "
                "unique players across observed teams; shrink toward 50 by minutes/(minutes+450); "
                "minutes-weighted squad mean; ELO population midrank; renormalize available component weights",
                sources=("team_strengths.elo_raw", "player_event_scores.final_points", "player_stats.team_id"),
                exclusions=("season achievement/collective bonuses", "unverified appearances", "future/live fixtures"),
                attribution="Physical starting season; verified appearance team; catalog player position",
                fallback="Previous physical season per missing component only; historical squad, not current roster",
                caveats=(
                    "Individual SFA includes M1/context and individual bonuses; "
                    "not independent strength; NEVER feeds M1",
                    "Percentiles are relative to observed participant population, not calibrated predictions",
                    "Coverage measures scored appearances, not roster completeness or availability",
                    "ELO summaries have unknown update freshness; "
                    "fallback and single-component scores are partial evidence",
                ),
            ), ranking=ranking,
        )
