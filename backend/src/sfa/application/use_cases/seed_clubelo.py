from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sfa.domain.scoring_ports import (
    ClubEloIdentityDTO,
    ClubEloProviderPort,
    ClubEloRatingDTO,
    ClubEloSourceDTO,
    EloSeedProvenanceDTO,
    ManualClubEloEntry,
    TeamEloSeedDTO,
    TeamStrengthRepositoryPort,
)

logger = logging.getLogger(__name__)

MAX_HISTORY_STALENESS_DAYS = 365
MAX_HISTORY_CONCURRENCY = 5


@dataclass(frozen=True)
class ClubEloSeedResolution:
    team_name: str
    status: str
    elo_raw: float | None
    source: str | None
    blocker: str | None


@dataclass(frozen=True)
class SeedClubEloResult:
    date_str: str
    season: str
    cutoff: date | None
    total_teams: int
    matched: int
    unmatched: list[str]
    coverage_pct: float
    source_counts: dict[str, int]
    history_requests: int
    blockers: list[str]
    resolutions: list[ClubEloSeedResolution]
    dry_run: bool
    status: str
    error: str | None
    provider_error: bool = False


@dataclass(frozen=True)
class _ResolvedSeed:
    elo_raw: float
    source: str
    source_reference: str
    provenance: EloSeedProvenanceDTO


class SeedClubEloUseCase:
    def __init__(
        self,
        repo: TeamStrengthRepositoryPort,
        provider: ClubEloProviderPort,
        calculator,
    ) -> None:
        self._repo = repo
        self._provider = provider
        self._calculator = calculator

    async def execute(
        self,
        date_str: str,
        season: str,
        manual_entries: list[ManualClubEloEntry] | None = None,
        dry_run: bool = True,
    ) -> SeedClubEloResult:
        try:
            cutoff = date.fromisoformat(date_str)
        except ValueError:
            return self._failed(date_str, season, None, dry_run, ["Invalid cutoff date"])

        team_name_id_map = await self._repo.get_team_name_id_map(season, "club")
        sfa_team_names = list(team_name_id_map)
        first_fixture_at = await self._repo.get_first_fixture_at(season, "club")
        if first_fixture_at is None:
            return self._failed(
                date_str,
                season,
                cutoff,
                dry_run,
                ["No club fixtures found for season"],
                total_teams=len(sfa_team_names),
            )

        expected_cutoff = first_fixture_at.astimezone(timezone.utc).date() - timedelta(days=1)
        if cutoff != expected_cutoff:
            return self._failed(
                date_str,
                season,
                cutoff,
                dry_run,
                [f"Invalid cutoff: expected {expected_cutoff}, received {cutoff}"],
                total_teams=len(sfa_team_names),
            )

        manual_by_team, manual_blockers = self._validate_manual_entries(
            manual_entries or [],
            team_name_id_map,
            cutoff,
        )
        if manual_blockers:
            return self._failed(
                date_str,
                season,
                cutoff,
                dry_run,
                manual_blockers,
                total_teams=len(sfa_team_names),
            )

        try:
            snapshot = await self._provider.fetch_snapshot(date_str)
            seeds_by_team = self._resolve_snapshot(snapshot, sfa_team_names, cutoff)
            resolution_status: dict[str, tuple[str, str | None]] = {
                team_name: ("snapshot", None) for team_name in seeds_by_team
            }

            history_targets = [
                identity
                for team_name in sfa_team_names
                if team_name not in seeds_by_team
                if (identity := self._provider.get_history_identity(team_name)) is not None
            ]
            histories = await self._fetch_histories(history_targets)
            for identity, history in histories:
                resolved, status, blocker = self._resolve_history(
                    identity,
                    history,
                    cutoff,
                )
                resolution_status[identity.sfa_team_name] = (status, blocker)
                if resolved is not None:
                    seeds_by_team[identity.sfa_team_name] = resolved

            blockers: list[str] = []
            for team_name, manual_entry in manual_by_team.items():
                if team_name in seeds_by_team:
                    blockers.append(
                        f"Manual entry cannot replace automatic seed for {team_name}"
                    )
                    continue
                seeds_by_team[team_name] = self._manual_seed(manual_entry, cutoff)
                resolution_status[team_name] = ("manual", None)

            unmatched = sorted(set(sfa_team_names) - set(seeds_by_team))
            for team_name in unmatched:
                status, blocker = resolution_status.get(
                    team_name,
                    ("unresolved", "No verified ClubElo identity or manual override"),
                )
                blockers.append(f"{team_name}: {blocker or status}")

            resolutions = [
                ClubEloSeedResolution(
                    team_name=team_name,
                    status=(
                        seeds_by_team[team_name].source
                        if team_name in seeds_by_team
                        else resolution_status.get(team_name, ("unresolved", None))[0]
                    ),
                    elo_raw=(
                        seeds_by_team[team_name].elo_raw
                        if team_name in seeds_by_team
                        else None
                    ),
                    source=(
                        seeds_by_team[team_name].source
                        if team_name in seeds_by_team
                        else None
                    ),
                    blocker=resolution_status.get(team_name, ("", None))[1],
                )
                for team_name in sorted(sfa_team_names)
            ]
            source_counts = self._source_counts(seeds_by_team)
            total = len(sfa_team_names)
            matched = len(seeds_by_team)
            coverage = round((matched / total * 100.0) if total else 100.0, 2)

            if blockers:
                return SeedClubEloResult(
                    date_str=date_str,
                    season=season,
                    cutoff=cutoff,
                    total_teams=total,
                    matched=matched,
                    unmatched=unmatched,
                    coverage_pct=coverage,
                    source_counts=source_counts,
                    history_requests=len(history_targets),
                    blockers=blockers,
                    resolutions=resolutions,
                    dry_run=dry_run,
                    status="failed",
                    error=f"Missing ClubElo seed for {len(unmatched)} active teams",
                )

            if not dry_run:
                await self._persist(
                    seeds_by_team,
                    team_name_id_map,
                    season,
                    cutoff,
                )

            logger.info(
                "[SeedClubEloUseCase] date=%s season=%s dry_run=%s matched=%d",
                date_str,
                season,
                dry_run,
                matched,
            )
            return SeedClubEloResult(
                date_str=date_str,
                season=season,
                cutoff=cutoff,
                total_teams=total,
                matched=matched,
                unmatched=[],
                coverage_pct=coverage,
                source_counts=source_counts,
                history_requests=len(history_targets),
                blockers=[],
                resolutions=resolutions,
                dry_run=dry_run,
                status="completed",
                error=None,
            )
        except Exception as exc:
            logger.error("[SeedClubEloUseCase] Failed date=%s season=%s: %s", date_str, season, exc)
            return self._failed(
                date_str,
                season,
                cutoff,
                dry_run,
                [str(exc)],
                total_teams=len(sfa_team_names),
                provider_error=True,
            )

    def _resolve_snapshot(
        self,
        snapshot: ClubEloSourceDTO,
        sfa_team_names: list[str],
        cutoff: date,
    ) -> dict[str, _ResolvedSeed]:
        resolved: dict[str, _ResolvedSeed] = {}
        for entry in snapshot.ratings:
            if (
                entry.valid_from is None
                or entry.valid_to is None
                or not entry.valid_from <= cutoff <= entry.valid_to
            ):
                continue
            sfa_name = self._provider.resolve_team_name(entry.club_name, sfa_team_names)
            if sfa_name is None or sfa_name in resolved or entry.elo <= 0:
                continue
            resolved[sfa_name] = _ResolvedSeed(
                elo_raw=entry.elo,
                source="clubelo_snapshot",
                source_reference=snapshot.source_reference,
                provenance=self._provenance(
                    "clubelo_snapshot",
                    entry,
                    snapshot,
                    cutoff,
                    0,
                ),
            )
        return resolved

    async def _fetch_histories(
        self,
        identities: list[ClubEloIdentityDTO],
    ) -> list[tuple[ClubEloIdentityDTO, ClubEloSourceDTO]]:
        semaphore = asyncio.Semaphore(MAX_HISTORY_CONCURRENCY)

        async def fetch(identity: ClubEloIdentityDTO):
            async with semaphore:
                source = await self._provider.fetch_history(identity.clubelo_identifier)
            return identity, source

        return await asyncio.gather(*(fetch(identity) for identity in identities))

    def _resolve_history(
        self,
        identity: ClubEloIdentityDTO,
        source: ClubEloSourceDTO,
        cutoff: date,
    ) -> tuple[_ResolvedSeed | None, str, str | None]:
        eligible = [
            row
            for row in source.ratings
            if row.club_name == identity.clubelo_identifier
            and row.country == identity.expected_country
            and row.elo > 0
            and row.valid_from is not None
            and row.valid_to is not None
            and row.valid_from <= row.valid_to
            and row.valid_from <= cutoff
        ]
        if not eligible:
            return None, "no_history", "No valid authoritative ClubElo history"

        latest_from = max(row.valid_from for row in eligible if row.valid_from is not None)
        latest = [row for row in eligible if row.valid_from == latest_from]
        unique = {
            (row.club_name, row.country, row.elo, row.valid_to)
            for row in latest
        }
        if len(unique) != 1:
            return None, "ambiguous", "Conflicting latest ClubElo history rows"

        row = latest[0]
        assert row.valid_to is not None
        history_age_days = max(0, (cutoff - row.valid_to).days)
        if history_age_days > MAX_HISTORY_STALENESS_DAYS:
            return (
                None,
                "stale",
                f"ClubElo history is {history_age_days} days old (max 365)",
            )

        method = "clubelo_history" if history_age_days == 0 else "clubelo_history_prior"
        return (
            _ResolvedSeed(
                elo_raw=row.elo,
                source=method,
                source_reference=source.source_reference,
                provenance=self._provenance(
                    method,
                    row,
                    source,
                    cutoff,
                    history_age_days,
                ),
            ),
            method,
            None,
        )

    def _manual_seed(
        self,
        entry: ManualClubEloEntry,
        cutoff: date,
    ) -> _ResolvedSeed:
        return _ResolvedSeed(
            elo_raw=entry.elo_raw,
            source="manual_override",
            source_reference=entry.source_reference,
            provenance=EloSeedProvenanceDTO(
                resolution_method="manual_override",
                cutoff=cutoff,
                source_reference=entry.source_reference,
                reason=entry.reason,
                source_date=entry.source_date,
                approved_by=entry.approved_by,
            ),
        )

    async def _persist(
        self,
        seeds_by_team: dict[str, _ResolvedSeed],
        team_name_id_map: dict[str, int],
        season: str,
        cutoff: date,
    ) -> None:
        effective_at = datetime.combine(cutoff, datetime.min.time(), tzinfo=timezone.utc)
        for sfa_name, seed_data in seeds_by_team.items():
            team_id = team_name_id_map[sfa_name]
            competition_ids = await self._repo.get_active_competition_ids_for_team(team_id, season)
            await self._repo.upsert_team_elo_seed(
                TeamEloSeedDTO(
                    team_id=team_id,
                    season=season,
                    participant_kind="club",
                    elo_raw=seed_data.elo_raw,
                    effective_at=effective_at,
                    source=seed_data.source,
                    source_reference=seed_data.source_reference,
                    provenance=seed_data.provenance,
                )
            )
            await self._repo.upsert_team_elo(
                team_id=team_id,
                season=season,
                elo_raw=seed_data.elo_raw,
                strength_normalized=self._calculator.normalize(seed_data.elo_raw),
                source="clubelo_seed",
                competition_ids=competition_ids,
                elo_seed_raw=seed_data.elo_raw,
            )

    @staticmethod
    def _validate_manual_entries(
        entries: list[ManualClubEloEntry],
        team_name_id_map: dict[str, int],
        cutoff: date,
    ) -> tuple[dict[str, ManualClubEloEntry], list[str]]:
        result: dict[str, ManualClubEloEntry] = {}
        blockers: list[str] = []
        for entry in entries:
            if entry.team_name in result:
                blockers.append(f"Duplicate manual entry for {entry.team_name}")
            elif entry.team_name not in team_name_id_map:
                blockers.append(f"Manual team is outside the pool: {entry.team_name}")
            elif entry.elo_raw <= 0:
                blockers.append(f"Manual ELO must be positive: {entry.team_name}")
            elif entry.source_date > cutoff:
                blockers.append(f"Manual source date is after cutoff: {entry.team_name}")
            elif not all((entry.reason.strip(), entry.source_reference.strip(), entry.approved_by.strip())):
                blockers.append(f"Manual evidence is incomplete: {entry.team_name}")
            else:
                result[entry.team_name] = entry
        return result, blockers

    @staticmethod
    def _provenance(
        method: str,
        rating: ClubEloRatingDTO,
        source: ClubEloSourceDTO,
        cutoff: date,
        history_age_days: int,
    ) -> EloSeedProvenanceDTO:
        return EloSeedProvenanceDTO(
            resolution_method=method,
            cutoff=cutoff,
            source_reference=source.source_reference,
            source_entity=rating.club_name,
            source_country=rating.country,
            source_valid_from=rating.valid_from,
            source_valid_to=rating.valid_to,
            history_age_days=history_age_days,
            payload_sha256=source.payload_sha256,
        )

    @staticmethod
    def _source_counts(seeds: dict[str, _ResolvedSeed]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for seed in seeds.values():
            counts[seed.source] = counts.get(seed.source, 0) + 1
        return counts

    @staticmethod
    def _failed(
        date_str: str,
        season: str,
        cutoff: date | None,
        dry_run: bool,
        blockers: list[str],
        total_teams: int = 0,
        provider_error: bool = False,
    ) -> SeedClubEloResult:
        return SeedClubEloResult(
            date_str=date_str,
            season=season,
            cutoff=cutoff,
            total_teams=total_teams,
            matched=0,
            unmatched=[],
            coverage_pct=0.0,
            source_counts={},
            history_requests=0,
            blockers=blockers,
            resolutions=[],
            dry_run=dry_run,
            status="failed",
            error=blockers[0] if blockers else "ClubElo seed failed",
            provider_error=provider_error,
        )
