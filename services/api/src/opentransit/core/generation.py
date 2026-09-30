"""Fixed M1 generation; managed activation arrives in M2."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("An explicit timezone offset is required")
    return result


@dataclass(frozen=True)
class Generation:
    id: str
    built_at: datetime
    validated_at: datetime
    coverage_from: datetime
    coverage_until: datetime
    engine_digest: str
    mode: str = "real"

    @classmethod
    def load(cls, path: Path) -> Generation:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["schemaVersion"] != 1 or data["state"] != "ready":
            raise ValueError("Generation is not ready or uses an unsupported schema")
        digest = data["engineDigest"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise ValueError("A pinned engine digest is required")
        result = cls(
            id=data["generationId"],
            built_at=instant(data["builtAt"]),
            validated_at=instant(data["validatedAt"]),
            coverage_from=instant(data["coverage"]["from"]),
            coverage_until=instant(data["coverage"]["until"]),
            engine_digest=digest,
            mode=data.get("mode", "real"),
        )
        if result.coverage_from >= result.coverage_until:
            raise ValueError("Generation has no service coverage")
        if result.mode not in {"real", "fixture"}:
            raise ValueError("Unknown data mode")
        return result

    def contains(self, time: datetime) -> bool:
        return self.coverage_from <= time < self.coverage_until

    def freshness(self, now: datetime) -> str:
        age = now - self.validated_at
        if age >= timedelta(days=7):
            return "expired"
        if age >= timedelta(hours=48):
            return "stale"
        if age >= timedelta(hours=30):
            return "aging"
        return "current"
