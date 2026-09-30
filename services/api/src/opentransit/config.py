import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    manifest_path: Path
    motis_url: str = "http://127.0.0.1:58081"
    engine_timeout_seconds: float = 1.2
    journey_deadline_seconds: float = 1.5
    playground_enabled: bool = False

    def __post_init__(self) -> None:
        url = urlsplit(self.motis_url)
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "motis"}:
            raise ValueError("MOTIS must be the local engine (localhost or Compose motis)")
        if url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("MOTIS URL must contain only a local origin")
        if not 0 < self.engine_timeout_seconds < self.journey_deadline_seconds <= 10:
            raise ValueError("Invalid engine timeout or journey deadline")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            manifest_path=Path(os.getenv("OPENTRANSIT_MANIFEST", ".runtime/m1/manifest.json")),
            motis_url=os.getenv("OPENTRANSIT_MOTIS_URL", "http://127.0.0.1:58081"),
            playground_enabled=os.getenv("OPENTRANSIT_PLAYGROUND", "0") == "1",
        )
