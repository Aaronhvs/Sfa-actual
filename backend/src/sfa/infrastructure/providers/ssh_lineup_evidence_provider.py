"""Bounded GET-only transport using the configured API account inside the VPS.

No provider retries, database imports, Redis writes or remote files. Credentials
and personal account fields never leave the remote process.
"""

import asyncio
import json
import re

from sfa.domain.player_positions.ports import LineupEvidenceResponse

_REMOTE = '''import asyncio,json,sys
from datetime import datetime,timezone
import httpx
from sfa.core.config import get_settings

async def main():
    fixture_id = int(sys.argv[1])
    settings = get_settings()
    result = {"fixture_id": fixture_id or None, "http_status": 0, "body": "{}",
              "fetched_at": datetime.now(timezone.utc).isoformat(),
              "daily_remaining": None, "minute_remaining": None, "minute_limit": None,
              "transport_error": None}
    try:
        async with httpx.AsyncClient(base_url=settings.API_FOOTBALL_BASE_URL,
            headers={"x-apisports-key":settings.API_FOOTBALL_KEY},timeout=20,
            follow_redirects=False) as client:
            response = await client.get("/fixtures/lineups" if fixture_id else "/status",
                params={"fixture":fixture_id} if fixture_id else None)
        result["http_status"] = response.status_code
        for field,header in (("daily_remaining","x-ratelimit-requests-remaining"),
                             ("minute_remaining","x-ratelimit-remaining"),
                             ("minute_limit","x-ratelimit-limit")):
            value = response.headers.get(header, "")
            result[field] = int(value) if value.isdigit() else None
        if fixture_id:
            result["body"] = response.text
        else:
            data = response.json()
            account = data.get("response") or {}
            result["body"] = json.dumps({"errors":bool(data.get("errors")),
                "active":(account.get("subscription") or {}).get("active"),
                "requests":account.get("requests")})
    except Exception as exc:
        result["transport_error"] = type(exc).__name__
    print(json.dumps(result))

asyncio.run(main())
'''


class SshLineupEvidenceProvider:
    def __init__(self, host: str, container: str = "backend-api-1"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", host):
            raise ValueError("Expected a configured SSH host alias")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", container):
            raise ValueError("Invalid container name")
        self._host = host
        self._container = container

    async def status(self) -> LineupEvidenceResponse:
        return await self._request(0)

    async def fetch_lineups(self, fixture_id: int) -> LineupEvidenceResponse:
        if type(fixture_id) is not int or fixture_id <= 0:
            raise ValueError("Invalid fixture identity")
        return await self._request(fixture_id)

    async def _request(self, fixture_id: int) -> LineupEvidenceResponse:
        await asyncio.sleep(1)
        process = await asyncio.create_subprocess_exec(
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", self._host,
            f"docker exec -i {self._container} python - {fixture_id}",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(_REMOTE.encode()), timeout=40)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("SSH evidence transport timed out; attempt must not be retried implicitly") from None
        if process.returncode:
            raise RuntimeError("SSH evidence transport failed; remote stderr withheld")
        return LineupEvidenceResponse(**json.loads(stdout.decode("utf-8")))
