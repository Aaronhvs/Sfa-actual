"""Import retained provider or reviewed public-name batches; resumable, zero API calls.

Input: {provider,source_ref,captured_at,profiles:[{external_id,display_name?,
first_name?,last_name?,full_name?}]}. Reviewed provenance must include actor and
official URL in source_ref. One committed batch per invocation; replay is safe.
"""
import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sfa.core.dependencies import get_enrich_player_name_aliases_use_case
from sfa.domain.player_name_aliases import PlayerNameProfileDTO
from sfa.infrastructure.database import AsyncSessionLocal, engine


async def run(path):
    data = json.loads(Path(path).read_text("utf8"))
    if len(data["profiles"]) > 1000:
        raise ValueError("Import at most 1000 identities per checkpoint")
    if data["provider"] == "official-club-reviewed" and (
            "https://" not in data["source_ref"] or "actor=" not in data["source_ref"]):
        raise ValueError("Reviewed aliases require the official source URL and reviewer")
    profiles = tuple(PlayerNameProfileDTO(**p) for p in data["profiles"])
    async with AsyncSessionLocal() as session:
        result = await get_enrich_player_name_aliases_use_case(session).execute(profiles,
            provider=data["provider"], source_ref=data["source_ref"],
            captured_at=datetime.fromisoformat(data["captured_at"]))
        await session.commit()
        print(json.dumps(asdict(result)))
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    asyncio.run(run(parser.parse_args().input))
