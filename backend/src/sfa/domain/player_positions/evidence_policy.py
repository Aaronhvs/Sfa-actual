"""Pure acquisition selection and explicit provider-version precedence."""
from collections import defaultdict
from datetime import datetime
from sfa.domain.player_positions.publication import canonical, digest


def provider_claim_hash(payload):
    def players(start):
        values = payload.get('startXI',payload.get('start_xi',[])) if start else payload.get('substitutes',[])
        values = [p.get('player',p) for p in values]
        return sorted(((p.get('id',p.get('external_id')),p.get('grid'),p.get('pos',p.get('position')))
                       for p in values if p.get('id',p.get('external_id'))),key=canonical)
    return digest({'formation':payload.get('formation'),'start':players(True),'bench':players(False)})


def retained_provider_versions(snapshot, supplementary=()):
    """Rehydrate real provider authority from the durable arbitration history."""
    revisions = defaultdict(list)
    for item in snapshot.get('lineup_arbitrations',[]):
        revisions[item['fixture_id'],item['team_id']].append(item)
    authoritative = {}
    for versions in revisions.values():
        latest = max(datetime.fromisoformat(v['fetched_at']) for v in versions)
        for version in versions:
            if datetime.fromisoformat(version['fetched_at']) == latest:
                authoritative[version['active_snapshot_id']] = version
    values=[]
    for item in tuple(snapshot['snapshots'])+tuple(supplementary):
        revision=authoritative.get(item['id'])
        values.append(item | {'authority':'api-football-direct-validated','fetched_at':revision['fetched_at']}
                      if revision else item)
    return active_provider_versions(tuple(values))


def provider_family(value: str | None) -> str | None:
    return {"G": "GK", "GOALKEEPER": "GK", "D": "DC", "DEFENDER": "DC",
            "M": "MC", "MIDFIELDER": "MC", "F": "DEL", "FORWARD": "DEL"}.get(
                (value or "").strip().upper())


def acquisition_tier(row: dict, matches: int) -> int | None:
    if row["appearances"] < 3:
        return None
    if row["rank"] <= 300 and row["status"] in {"ambiguous", "insufficient_evidence"}:
        return 1
    if row["status"] == "insufficient_evidence" and matches >= 6:
        return 2
    return None


def active_provider_versions(snapshots: tuple[dict, ...]) -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    """Select validated direct revisions; preserve originals and tied conflicts.

    Callers validate the complete XI and fixture/team identity before granting
    authority. A cache receipt timestamp alone never grants authority.
    """
    grouped = defaultdict(list)
    for item in snapshots:
        grouped[item["fixture_id"], item["team_id"]].append(item)
    active, supersessions = [], []
    for key, versions in grouped.items():
        authoritative = [v for v in versions if v.get("authority") == "api-football-direct-validated"
                         and v.get("fetched_at")]
        if not authoritative:
            active.extend(versions)
            continue
        latest = max(datetime.fromisoformat(v["fetched_at"].replace("Z", "+00:00")) for v in authoritative)
        winners = [v for v in authoritative
                   if datetime.fromisoformat(v["fetched_at"].replace("Z", "+00:00")) == latest]
        if len({provider_claim_hash(v['payload']) if 'payload' in v else v['payload_hash'] for v in winners}) != 1:
            active.extend(versions)
            continue
        winner = min(winners,key=lambda v:str(v['id']))
        active.append(winner)
        supersessions.append({"fixture_id": key[0], "team_id": key[1], "active_id": winner["id"],
                              "active_hash": winner["payload_hash"], "fetched_at": winner["fetched_at"],
                              "supersedes": [v["id"] for v in versions if v is not winner],
                              "reason": "latest_validated_direct_provider_revision"})
    return tuple(active), tuple(supersessions)
