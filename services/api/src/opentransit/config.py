import ipaddress
import os
import sys
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
    source_check_path: Path | None = None
    probe_path: Path | None = None
    current_binding_path: Path | None = None
    managed_root: Path | None = None
    ack_dir: Path | None = None
    photon_url: str | None = None
    photon_admin_url: str | None = None
    # Bounded geocoder warm-up before a snapshot is published, then background recovery.
    warmup_attempts: int = 5
    warmup_retry_seconds: float = 0.5
    warmup_recovery_seconds: float = 5.0

    def __post_init__(self) -> None:
        if (
            not 1 <= self.warmup_attempts <= 20
            or not 0 <= self.warmup_retry_seconds <= 10
            or not 0 < self.warmup_recovery_seconds <= 300
        ):
            raise ValueError("Invalid geocoder warm-up bounds")
        url = urlsplit(self.motis_url)
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "motis"}:
            raise ValueError("MOTIS must be the local engine (localhost or Compose motis)")
        if url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("MOTIS URL must contain only a local origin")
        if not 0 < self.engine_timeout_seconds < self.journey_deadline_seconds <= 10:
            raise ValueError("Invalid engine timeout or journey deadline")
        if (self.photon_url is None) != (self.photon_admin_url is None):
            raise ValueError("Photon query and admin origins must be configured together")
        for label, value in (("Photon", self.photon_url), ("Photon admin", self.photon_admin_url)):
            if value is None:
                continue
            parsed = urlsplit(value)
            if (
                parsed.scheme != "http"
                or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.port is None
                or parsed.path not in {"", "/"}
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"{label} origin must be an explicit loopback HTTP origin")
        managed_values = (self.current_binding_path, self.managed_root, self.ack_dir)
        if any(value is not None for value in managed_values):
            if not all(value is not None for value in managed_values):
                raise ValueError(
                    "OPENTRANSIT_CURRENT_BINDING, OPENTRANSIT_MANAGED_ROOT, and "
                    "OPENTRANSIT_ACK_DIR must be configured together"
                )
            if sys.platform != "linux":
                raise ValueError(
                    "Managed local activation requires Linux symlink and SIGUSR1 support"
                )
            if (
                self.current_binding_path is None
                or self.managed_root is None
                or self.ack_dir is None
            ):
                raise ValueError("Managed activation paths are incomplete")
            for path in (self.current_binding_path, self.managed_root, self.ack_dir):
                if not path.is_absolute():
                    raise ValueError("Managed activation paths must be absolute")
            root = self.managed_root.resolve(strict=True)
            if self.current_binding_path.parent.resolve(strict=True) != root:
                raise ValueError("Current binding pointer must be directly inside managed root")
            host = url.hostname
            try:
                loopback = ipaddress.ip_address(host).is_loopback if host else False
            except ValueError:
                loopback = host == "localhost"
            if not loopback:
                raise ValueError("Managed local activation requires a loopback MOTIS URL")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            manifest_path=Path(os.getenv("OPENTRANSIT_MANIFEST", ".runtime/m1/manifest.json")),
            motis_url=os.getenv("OPENTRANSIT_MOTIS_URL", "http://127.0.0.1:58081"),
            playground_enabled=os.getenv("OPENTRANSIT_PLAYGROUND", "0") == "1",
            source_check_path=Path(os.environ["OPENTRANSIT_SOURCE_CHECK"])
            if os.getenv("OPENTRANSIT_SOURCE_CHECK")
            else None,
            probe_path=Path(os.environ["OPENTRANSIT_PROBE"])
            if os.getenv("OPENTRANSIT_PROBE")
            else None,
            current_binding_path=Path(os.environ["OPENTRANSIT_CURRENT_BINDING"])
            if os.getenv("OPENTRANSIT_CURRENT_BINDING")
            else None,
            managed_root=Path(os.environ["OPENTRANSIT_MANAGED_ROOT"])
            if os.getenv("OPENTRANSIT_MANAGED_ROOT")
            else None,
            ack_dir=Path(os.environ["OPENTRANSIT_ACK_DIR"])
            if os.getenv("OPENTRANSIT_ACK_DIR")
            else None,
            photon_url=os.getenv("OPENTRANSIT_PHOTON_URL"),
            photon_admin_url=os.getenv("OPENTRANSIT_PHOTON_ADMIN_URL"),
        )
