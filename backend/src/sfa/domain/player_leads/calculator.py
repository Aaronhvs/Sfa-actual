from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping, Sequence

from sfa.domain.player_leads.models import (
    LeadGroup,
    LeadGroupKind,
    LeadMetric,
    LeadSample,
    LeadThreshold,
    PlayerLead,
    PlayerLeadsSnapshot,
)
from sfa.domain.player_leads.policy import CATALOG, LeadPolicy, MetricDefinition
from sfa.domain.season_scope import ScopeKind

_RANK_PRECISION = 6

Group = tuple[LeadGroup, list[LeadSample]]


class PlayerLeadsCalculator:
    """Pure domain service: builds comparison groups and keeps every podium place of every player."""

    def __init__(self, policy: LeadPolicy | None = None, catalog: Sequence[MetricDefinition] = CATALOG) -> None:
        self._policy = policy or LeadPolicy()
        self._catalog = tuple(catalog)

    @property
    def policy(self) -> LeadPolicy:
        return self._policy

    def calculate(
        self,
        *,
        scope_key: str,
        scope_kind: ScopeKind,
        samples: Sequence[LeadSample],
        scope_positions: Mapping[int, str | None],
        rules_version_id: int | None,
        sfa_available: bool,
    ) -> PlayerLeadsSnapshot:
        tournament = scope_kind == ScopeKind.TOURNAMENT
        best: dict[int, dict[LeadMetric, PlayerLead]] = defaultdict(dict)
        for group, members in self.build_groups(samples, scope_positions, tournament):
            for definition in self._catalog:
                if definition.is_sfa and not sfa_available:
                    continue
                if group.kind.is_position and (
                    not definition.splits_by_position or group.position not in definition.positions
                ):
                    continue
                population = [member for member in members if member.position in definition.positions]
                for player_id, lead in self.rank_group(definition, group, population, tournament):
                    current = best[player_id].get(lead.metric)
                    if current is None or lead.exceptional_key < current.exceptional_key:
                        best[player_id][lead.metric] = lead

        leads_by_player = {
            player_id: tuple(sorted(by_metric.values(), key=lambda lead: lead.exceptional_key))
            for player_id, by_metric in best.items()
        }
        return PlayerLeadsSnapshot(self._policy.policy_version, scope_key, rules_version_id, leads_by_player)

    def build_groups(
        self, samples: Sequence[LeadSample], scope_positions: Mapping[int, str | None], tournament: bool,
    ) -> list[Group]:
        groups: list[Group] = []
        by_source: dict[tuple[str | None, int | None], list[LeadSample]] = defaultdict(list)
        for sample in samples:
            by_source[(sample.season, sample.competition_id)].append(sample)

        for (season, competition_id), members in sorted(by_source.items(), key=lambda item: str(item[0])):
            if not self._policy.competition_qualifies(max(member.minutes for member in members), tournament):
                continue
            name = members[0].competition_name
            groups.append((LeadGroup(LeadGroupKind.COMPETITION, season, competition_id, name), members))
            groups.extend(
                (LeadGroup(LeadGroupKind.COMPETITION_POSITION, season, competition_id, name, position), subset)
                for position, subset in _by_position(members)
            )

        if not tournament:
            club_samples = [sample for sample in samples if sample.participant_kind == "club"]
            if len({(sample.season, sample.competition_id) for sample in club_samples}) >= 2:
                merged = _merge_by_player(club_samples, scope_positions)
                groups.append((LeadGroup(LeadGroupKind.SCOPE), merged))
                groups.extend(
                    (LeadGroup(LeadGroupKind.SCOPE_POSITION, position=position), subset)
                    for position, subset in _by_position(merged)
                )
        return groups

    def rank_group(
        self,
        definition: MetricDefinition,
        group: LeadGroup,
        population: Sequence[LeadSample],
        tournament: bool,
    ) -> list[tuple[int, PlayerLead]]:
        if not population:
            return []
        threshold, qualifies = self._threshold(definition, population, tournament)
        qualified = [sample for sample in population if qualifies(sample)]
        if len(qualified) < self._policy.min_group_size(group.kind.is_position):
            return []

        scored = [(definition.ranking_value(sample), sample) for sample in qualified]
        scored.sort(key=lambda item: (
            -item[0], -definition.numerator(item[1]), item[1].minutes, item[1].player_id,
        ))
        rounded = [round(value, _RANK_PRECISION) for value, _ in scored]
        counts: dict[float, int] = defaultdict(int)
        for value in rounded:
            counts[value] += 1

        leads: list[tuple[int, PlayerLead]] = []
        rank = 0
        for index, ((ranking_value, sample), key) in enumerate(zip(scored, rounded)):
            if index == 0 or key != rounded[index - 1]:
                rank = index + 1
            if rank > self._policy.max_rank_limit:
                break
            leads.append((sample.player_id, PlayerLead(
                metric=definition.metric,
                group=group,
                rank=rank,
                tied=counts[key] > 1,
                qualified_count=len(qualified),
                value=definition.value(sample),
                ranking_value=ranking_value,
                method=definition.method,
                numerator=float(definition.numerator(sample)),
                denominator=float(definition.denominator(sample)),
                threshold=threshold,
                details=definition.details(sample),
            )))
        return leads

    def _threshold(self, definition: MetricDefinition, population: Sequence[LeadSample], tournament: bool):
        """Minimums are computed over the whole eligible population before anyone is filtered out."""
        policy = self._policy
        if definition.is_sfa:
            min_minutes = policy.min_minutes(max(sample.big_minutes for sample in population), tournament)
            min_matches = policy.min_big_matches(tournament)
            threshold = LeadThreshold(min_minutes=min_minutes, min_events=min_matches)
            return threshold, lambda s: s.big_minutes >= min_minutes and s.big_matches >= min_matches

        min_minutes = policy.min_minutes(max(sample.minutes for sample in population), tournament)
        min_attempts: int | None = None
        if definition.attempts is not None and definition.attempts_floor is not None:
            min_attempts = policy.min_attempts(
                int(max(definition.attempts(sample) for sample in population)), definition.attempts_floor,
            )
        threshold = LeadThreshold(
            min_minutes=min_minutes,
            min_attempts=min_attempts,
            attempts_kind=definition.attempts_kind if min_attempts is not None else None,
            min_events=definition.min_events,
        )

        def qualifies(sample: LeadSample) -> bool:
            if sample.minutes < min_minutes:
                return False
            if min_attempts is not None and definition.attempts(sample) < min_attempts:
                return False
            if definition.min_events is not None and definition.events(sample) < definition.min_events:
                return False
            return True

        return threshold, qualifies


def _by_position(members: Iterable[LeadSample]) -> list[tuple[str, list[LeadSample]]]:
    grouped: dict[str, list[LeadSample]] = defaultdict(list)
    for member in members:
        if member.position is not None:
            grouped[member.position].append(member)
    return sorted(grouped.items())


def _merge_by_player(samples: Iterable[LeadSample], scope_positions: Mapping[int, str | None]) -> list[LeadSample]:
    merged: dict[int, LeadSample] = {}
    for sample in samples:
        current = merged.get(sample.player_id)
        if current is None:
            # Combining with an empty sample drops the source fields (season, competition).
            current = LeadSample(sample.player_id, None, None, None, None, sample.position)
        merged[sample.player_id] = current.combine(sample)
    return [
        sample.with_position(scope_positions.get(player_id, sample.position))
        for player_id, sample in sorted(merged.items())
    ]
