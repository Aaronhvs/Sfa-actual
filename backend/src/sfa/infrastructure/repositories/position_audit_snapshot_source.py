import hashlib
from pathlib import Path

from sfa.domain.player_positions.value_objects import PositionAuditSnapshot


class FilePositionAuditSnapshotSource:
    """Offline replay source with no database, Redis or HTTP dependency."""

    def __init__(self, path: Path):
        self._path = path

    async def load(self) -> PositionAuditSnapshot:
        raw = self._path.read_bytes()
        return PositionAuditSnapshot(raw.decode("utf-8-sig"), hashlib.sha256(raw).hexdigest())
