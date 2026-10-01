"""Fixed M1 generation; managed activation arrives in M2."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from opentransit.core.time import as_utc_instant

# Source-freshness states that /readyz and request handling treat as serviceable.
# Only "expired" (seven days or more, or a future-dated check) is rejected; the
# earlier states are served with warnings (docs/system-design.md section 9).
SERVICEABLE_FRESHNESS = frozenset({"current", "aging", "stale"})


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
    source_checked_at: datetime | None = None
    source_check_recorded: bool = False

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
            source_checked_at=instant(data["sourceCheckedAt"])
            if data.get("sourceCheckedAt")
            else None,
            source_check_recorded="sourceCheckedAt" in data,
        )
        if as_utc_instant(result.coverage_from) >= as_utc_instant(result.coverage_until):
            raise ValueError("Generation has no service coverage")
        if result.mode not in {"real", "fixture"}:
            raise ValueError("Unknown data mode")
        return result

    def contains(self, time: datetime) -> bool:
        instant_utc = as_utc_instant(time)
        return (
            as_utc_instant(self.coverage_from) <= instant_utc < as_utc_instant(self.coverage_until)
        )

    @property
    def freshness_basis(self) -> str:
        return "sourceCheckedAt" if self.source_check_recorded else "validatedAt"

    def freshness_checked_at(self) -> datetime | None:
        return self.source_checked_at if self.source_check_recorded else self.validated_at

    def freshness_serviceable(self, now: datetime) -> bool:
        return self.freshness(now) in SERVICEABLE_FRESHNESS

    def freshness(self, now: datetime) -> str:
        checked_at = self.freshness_checked_at()
        if checked_at is None:
            return "expired"
        age = as_utc_instant(now) - as_utc_instant(checked_at)
        if age < timedelta(minutes=-5):
            return "expired"
        if age >= timedelta(days=7):
            return "expired"
        if age >= timedelta(hours=48):
            return "stale"
        if age >= timedelta(hours=30):
            return "aging"
        return "current"
