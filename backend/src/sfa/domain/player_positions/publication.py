from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class PositionCorrectionRequest:
    player_id: int
    external_player_id: int
    team_id: int
    external_team_id: int
    season: str
    position: str
    fixture_ids: tuple[int, ...]
    accepted_at: str
    source_ref: str
    statement: str
    actor: str
    schema_version: int = 2
    current_reference_json: str | None = None

    @property
    def manifest_data(self):
        result = asdict(self)
        if self.schema_version == 1:
            result.pop('schema_version')
            result.pop('current_reference_json')
        return result

    def __post_init__(self):
        if self.schema_version not in {1, 2}:
            raise ValueError("Unsupported correction request version")
        if self.current_reference_json is not None:
            reference = json.loads(self.current_reference_json)
            if not all(reference.get(k) for k in ("position", "source_ref", "statement", "accepted_at", "evidence_ids")):
                raise ValueError("An optional current reference needs its own decision and evidence")
        for identity in (self.player_id, self.external_player_id, self.team_id, self.external_team_id,
                         *self.fixture_ids):
            if type(identity) is not int or identity <= 0:
                raise ValueError("Correction identities must be positive integer IDs")
        if not self.fixture_ids or tuple(sorted(set(self.fixture_ids))) != self.fixture_ids:
            raise ValueError("Correction requires a sorted, nonempty, unique fixture allowlist")
        if self.position not in {"DEL", "EXT", "MCO", "MC", "LAT", "DC"}:
            raise ValueError("Unsupported correction position")
        if datetime.fromisoformat(self.accepted_at).tzinfo is None:
            raise ValueError("Correction acceptance requires a timezone")
        if not all(v.strip() for v in (self.season, self.source_ref, self.statement, self.actor)):
            raise ValueError("Correction provenance is required")


@dataclass(frozen=True)
class PositionCorrectionCapture:
    source_json: str
    scores_json: str
    rollups_json: str
    engine_hash: str


@dataclass(frozen=True)
class PositionCorrectionPlan:
    request: PositionCorrectionRequest
    rules_version_id: int
    input_hash: str
    engine_hash: str
    event_changes_json: str
    rollup_changes_json: str
    dependencies_json: str
    report_json: str

    @property
    def manifest_hash(self) -> str:
        values = asdict(self)
        if self.request.schema_version == 1:
            values['request'].pop('schema_version')
            values['request'].pop('current_reference_json')
        return digest(values)

    @property
    def batch_id(self) -> str:
        return self.manifest_hash


@dataclass(frozen=True)
class PositionPublicationResult:
    batch_id: str
    status: str
    event_count: int
    rollup_count: int


@dataclass(frozen=True)
class SeasonPositionCorrectionPlan:
    scope_json: str
    rules_version_id: int
    accepted_at: str
    actor: str
    source_hash: str
    engine_hash: str
    decisions_json: str
    classifications_json: str
    event_changes_json: str
    rollup_changes_json: str
    bonus_changes_json: str
    evidence_json: str
    report_json: str
    schema_version: int = 2

    def __post_init__(self):
        scope = json.loads(self.scope_json)
        pairs = {(s['season'], c) for s in scope['sources'] for c in s['competition_ids']}
        if (self.schema_version != 2 or scope['key'] != 'season-2026' or not pairs
                or any(s != '2026' or type(c) is not int or c <= 0 or c == 350 for s,c in pairs)
                or scope.get('includes_world_cup') or not self.actor.strip()
                or not self.source_hash or not self.engine_hash or self.rules_version_id <= 0
                or datetime.fromisoformat(self.accepted_at).tzinfo is None):
            raise ValueError('Invalid season-2026 correction manifest scope/provenance')
        decisions = json.loads(self.decisions_json)
        mapped = {d['player_id']:d for d in decisions}
        if not decisions or len(mapped) != len(decisions) or any(
            d['position'] not in {'DC','LAT','MC','MCO','EXT','DEL'}
            or d['assertion_kind'] != 'curated_fixture_scoring_role' or d['season'] != '2026'
            or not d['fixture_ids'] or d['fixture_ids'] != sorted(set(d['fixture_ids'])) for d in decisions):
            raise ValueError('Manifest requires distinct explicit fixture scoring decisions')
        classifications = json.loads(self.classifications_json)
        competitions = sorted(c for _,c in pairs)
        if len(classifications) != len(decisions) or {c['player_id'] for c in classifications} != set(mapped) or any(
                c['scope_key'] != scope['key'] or c['scope_competition_ids'] != competitions
                or not set(c['competition_ids']).issubset(competitions)
                or c['position'] != mapped[c['player_id']]['position'] for c in classifications):
            raise ValueError('Scope classifications must match reviewed decisions and competition set')
        for encoded in (self.event_changes_json,self.rollup_changes_json,self.bonus_changes_json):
            changes = json.loads(encoded)
            if len({c['before']['id'] for c in changes}) != len(changes):
                raise ValueError('Manifest contains duplicate physical rows')
            for change in changes:
                before,after = change['before'],change['after']
                keys = ('id','player_id','competition_id','season','rules_version_id')
                if (any(before[k] != after[k] for k in keys) or (after['season'],after['competition_id']) not in pairs
                        or after['rules_version_id'] != self.rules_version_id):
                    raise ValueError('Correction row crosses the approved scope or identity')
        for change in json.loads(self.event_changes_json):
            before,after = change['before'],change['after']
            decision = mapped.get(after['player_id'])
            if (not decision or before['event_id'] != after['event_id'] or before['fixture_id'] != after['fixture_id']
                    or after['fixture_id'] not in decision['fixture_ids'] or after['position'] != decision['position']):
                raise ValueError('Event correction lacks its explicit fixture decision')

    @property
    def batch_id(self) -> str:
        return digest(asdict(self))

    @property
    def manifest_hash(self) -> str:
        return self.batch_id
