import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from sfa.domain.player_positions.ports import LineupEvidenceResponse


class FileLineupEvidenceArchive:
    """Atomic local checkpoints and content-addressed evidence, never published data."""

    def __init__(self, directory: Path):
        self._directory = directory
        self._lock_file = None

    async def acquire(self) -> None:
        if self._lock_file is not None:
            raise RuntimeError("Recovery archive is already in use")
        self._directory.mkdir(parents=True, exist_ok=True)
        lock_file = (self._directory / ".recovery.lock").open("a+b")
        if lock_file.seek(0, os.SEEK_END) == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock_file.close()
            raise RuntimeError("Recovery archive is already in use by another process") from None
        self._lock_file = lock_file

    async def release(self) -> None:
        if self._lock_file is not None:
            self._lock_file.close()
            self._lock_file = None

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    async def load_manifest(self) -> str | None:
        path = self._directory / "request-manifest.json"
        return path.read_text("utf-8") if path.exists() else None

    async def save_manifest(self, content: str) -> None:
        self._write(self._directory / "request-manifest.json", content)
        manifest = json.loads(content)
        self._write(self._directory / "requests.jsonl", "".join(
            json.dumps(record, sort_keys=True) + "\n" for record in manifest.get("requests", [])
        ))
        self._write(self._directory / "quota-summary.json", json.dumps({
            "http_cap": manifest["http_cap"], "daily_reserve": manifest["daily_reserve"],
            "attempts": len(manifest.get("requests", [])),
            "last_response": manifest.get("requests", [])[-1] if manifest.get("requests") else None,
        }, sort_keys=True, indent=2))

    async def load_response(self, fixture_id: int) -> LineupEvidenceResponse | None:
        index = self._directory / "responses" / f"{fixture_id}.json"
        if not index.exists():
            return None
        data = json.loads(index.read_text("utf-8"))
        metadata = data["response"]
        body = (self._directory / "payloads" / f"{fixture_id}-{data['sha256']}.json").read_bytes().decode("utf-8")
        if hashlib.sha256(body.encode()).hexdigest() != data["sha256"]:
            raise ValueError("Archived lineup payload hash mismatch")
        return LineupEvidenceResponse(body=body, **metadata)

    async def save_response(self, response: LineupEvidenceResponse) -> str:
        identity = response.fixture_id or 0
        digest = hashlib.sha256(response.body.encode()).hexdigest()
        index = self._directory / "responses" / f"{identity}.json"
        if identity and index.exists() and json.loads(index.read_text("utf-8"))["sha256"] != digest:
            self._write(self._directory / "payloads" / f"{identity}-{digest}.json", response.body)
            raise ValueError("Contradictory archived response; both payloads retained")
        self._write(self._directory / "payloads" / f"{identity}-{digest}.json", response.body)
        metadata = asdict(response)
        metadata.pop("body")
        self._write(index, json.dumps({"sha256": digest, "response": metadata}, sort_keys=True, indent=2))
        return digest

    async def save_snapshot(self, content: str) -> None:
        self._write(self._directory / "recovered-snapshot.json", content)
