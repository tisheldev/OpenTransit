"""Read-only lookup catalog for source-linked Photon address documents."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

CATALOG_SCHEMA_VERSION = 1
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OSM_TYPES = frozenset({"N", "W"})


class AddressCatalog:
    """Immutable SQLite view of the exact enriched Photon source dump."""

    def __init__(self, path: Path, expected_dump_sha256: str) -> None:
        if not isinstance(expected_dump_sha256, str) or not _SHA256.fullmatch(expected_dump_sha256):
            raise ValueError("Expected Photon dump SHA-256 is invalid")
        resolved = Path(path).resolve()
        uri = f"{resolved.as_uri()}?mode=ro&immutable=1"
        self._connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        try:
            user_version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            rows = dict(self._connection.execute("SELECT key, value FROM metadata"))
            if (
                user_version != CATALOG_SCHEMA_VERSION
                or rows.get("schema_version") != str(CATALOG_SCHEMA_VERSION)
                or rows.get("source_dump_sha256") != expected_dump_sha256
                or not _SHA256.fullmatch(rows.get("source_pbf_sha256", ""))
            ):
                raise ValueError("Address catalog metadata or source dump hash is invalid")
            count = self._connection.execute("SELECT COUNT(*) FROM places").fetchone()[0]
            if int(rows.get("record_count", "-1")) != count:
                raise ValueError("Address catalog record count does not match its metadata")
            self._metadata: Mapping[str, str] = MappingProxyType(rows)
        except (sqlite3.Error, TypeError, ValueError) as exc:
            self._connection.close()
            if isinstance(exc, ValueError):
                raise
            raise ValueError("Address catalog schema is invalid") from exc

    @property
    def metadata(self) -> Mapping[str, str]:
        return self._metadata

    @property
    def source_dump_sha256(self) -> str:
        return self._metadata["source_dump_sha256"]

    @property
    def source_pbf_sha256(self) -> str:
        return self._metadata["source_pbf_sha256"]

    @property
    def schema_version(self) -> int:
        return int(self._metadata["schema_version"])

    @property
    def record_count(self) -> int:
        return int(self._metadata["record_count"])

    def lookup(self, osm_type: str, full_osm_id: str) -> dict[str, Any] | None:
        if (
            osm_type not in _OSM_TYPES
            or not isinstance(full_osm_id, str)
            or not full_osm_id.isdigit()
        ):
            return None
        row = self._connection.execute(
            "SELECT payload_json FROM places WHERE osm_type = ? AND osm_id = ?",
            (osm_type, full_osm_id),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise ValueError("Address catalog row is malformed")
        return payload

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> AddressCatalog:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
