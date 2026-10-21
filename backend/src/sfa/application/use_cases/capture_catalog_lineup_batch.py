"""At most ten sequential, GET-only requests; evidence stays in a local archive."""
import json
from dataclasses import asdict, dataclass

from sfa.application.use_cases.recover_missing_lineups import _decode, _normalize
from sfa.domain.player_positions.ports import LineupEvidenceArchive, LineupEvidenceProvider


@dataclass(frozen=True)
class CatalogLineupBatchResult:
    state: str
    acquired_json: str
    requests: int


class CaptureCatalogLineupBatchUseCase:
    def __init__(self, provider: LineupEvidenceProvider, archive: LineupEvidenceArchive):
        self._provider = provider
        self._archive = archive

    async def execute(self, *, fixtures: tuple[dict, ...], input_sha256: str) -> CatalogLineupBatchResult:
        if not 1 <= len(fixtures) <= 10 or len({f["external_id"] for f in fixtures}) != len(fixtures):
            raise ValueError("A batch must contain 1..10 unique known fixtures")
        await self._archive.acquire()
        try:
            existing = await self._archive.load_manifest()
            manifest = json.loads(existing) if existing else {
                "input_sha256": input_sha256, "fixture_ids": [f["external_id"] for f in fixtures],
                "http_cap": 11, "daily_reserve": 100, "requests": [], "state": "planned",
            }
            if (manifest["input_sha256"] != input_sha256
                    or manifest["fixture_ids"] != [f["external_id"] for f in fixtures]):
                raise ValueError("Archive belongs to a different batch")

            async def checkpoint():
                await self._archive.save_manifest(json.dumps(manifest, indent=2))

            async def request(identity):
                record = {"fixture_id": identity, "state": "attempt_started"}
                manifest["requests"].append(record)
                await checkpoint()
                response = (await self._provider.status() if identity is None
                            else await self._provider.fetch_lineups(identity))
                digest = await self._archive.save_response(response)
                record.update({k: v for k, v in asdict(response).items() if k not in {"body", "fixture_id"}})
                record["response_fixture_id"] = response.fixture_id
                record.update(state="captured", sha256=digest, error=_decode(response)[1])
                await checkpoint()
                return response

            recovered, pending, archived_error = [], [], False
            for fixture in fixtures:
                saved = await self._archive.load_response(fixture["external_id"])
                if saved:
                    normalized, outcome = _normalize(saved, fixture)
                    if normalized:
                        recovered.append(normalized)
                    elif outcome != "provider_empty":
                        archived_error = True
                else:
                    pending.append(fixture)
            if any(r["state"] == "attempt_started" for r in manifest["requests"]):
                manifest["state"] = "uncertain_previous_attempt"
            elif archived_error:
                manifest["state"] = "archived_error_requires_review"
            elif not pending:
                manifest["state"] = "completed"
            elif manifest["requests"]:
                # Do not retry errors or consume another status beyond the frozen cap.
                manifest["state"] = "partial_requires_review"
            else:
                manifest["state"] = "running"
                quota = await request(None)
                status, error = _decode(quota)
                if error or status.get("active") is not True:
                    manifest["state"] = error or "access_unavailable"
                else:
                    for fixture in pending:
                        if any(v is None for v in (quota.daily_remaining, quota.minute_remaining, quota.minute_limit)):
                            manifest["state"] = "quota_unknown"
                            break
                        if quota.daily_remaining <= 100 or quota.minute_remaining <= 1 or quota.minute_limit <= 0:
                            manifest["state"] = "quota_margin_exhausted"
                            break
                        quota = await request(fixture["external_id"])
                        if quota.fixture_id != fixture["external_id"]:
                            manifest["state"] = "fixture_identity_mismatch"
                            break
                        normalized, outcome = _normalize(quota, fixture)
                        if normalized:
                            recovered.append(normalized)
                        elif outcome != "provider_empty":
                            manifest["state"] = outcome
                            break
                    else:
                        manifest["state"] = "completed"
            await checkpoint()
            return CatalogLineupBatchResult(manifest["state"], json.dumps(recovered), len(manifest["requests"]))
        finally:
            await self._archive.release()
