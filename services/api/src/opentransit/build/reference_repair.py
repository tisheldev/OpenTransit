"""Clone and repair legacy stop-name translation keys in a sealed generation."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from opentransit.build.generations import PARSER_VERSION, verify_artifacts
from opentransit.core.artifacts import file_sha256
from opentransit.reference import (
    COUNT_TABLES,
    ReferenceStore,
    _content_hash,
    _translation_rows,
    _validate_translation_rows,
)

REPAIR_POLICY = "gtfs-legacy-trans-id-exact-field-value-v1"


def _json_write(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _generation_id(identity: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _read_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("state") != "ready":
        raise ValueError("Parent generation is not sealed and ready")
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or manifest.get("generationId") != _generation_id(identity):
        raise ValueError("Parent generation identity is invalid")
    if identity.get("parserVersion") != manifest.get("parserVersion"):
        raise ValueError("Parent parser version differs from its identity")
    return manifest


def _parse_source(gtfs_zip: Path, expected_sha256: str) -> tuple[list[tuple], str]:
    actual = file_sha256(gtfs_zip)
    if actual != expected_sha256:
        raise ValueError("GTFS source archive hash differs from the sealed parent")
    with ZipFile(gtfs_zip) as archive:
        member = archive.getinfo("translations.txt")
        member_hash = hashlib.sha256(archive.read(member)).hexdigest()
        # This is intentionally the only GTFS member parsed by the repair.
        normalized_rows = list(_translation_rows(archive))
    if not normalized_rows:
        raise ValueError("GTFS translations member has no rows")
    return normalized_rows, member_hash


def _repair_database(
    database: Path,
    rows: list[tuple],
    generation_id: str,
    expected_source_sha256: str,
) -> tuple[str, int, dict[str, int]]:
    database.chmod(0o600)
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        values = {
            key: json.loads(value)
            for key, value in connection.execute("SELECT key, value FROM metadata")
        }
        if values.get("sourceSha256") != expected_source_sha256:
            raise ValueError("Reference database source hash differs from the sealed parent")
        previous_counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in COUNT_TABLES
        }
        connection.execute("DELETE FROM translations")
        _validate_translation_rows(connection, rows)
        connection.executemany(
            "INSERT INTO translations "
            "(table_name,lang,translation,field_name,record_id,record_sub_id,field_value,priority) "
            "VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        counts = dict(previous_counts)
        counts["translations"] = len(rows)
        # Recompute canonical reference content once after replacement.
        content_hash = _content_hash(connection)
        metadata = {
            **values,
            "generationId": generation_id,
            "contentSha256": content_hash,
            "counts": counts,
        }
        connection.executemany(
            "INSERT INTO metadata(key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [(key, json.dumps(value, sort_keys=True)) for key, value in metadata.items()],
        )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("Repaired reference failed SQLite integrity verification")
        return content_hash, len(rows), previous_counts
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def repair_reference_generation(
    parent_generation: Path,
    gtfs_zip: Path,
    output_generation: Path,
) -> Path:
    """Create an immutable parser-v2 generation with exact legacy translations.

    The parent, source ZIP, config and graph are read-only. The output must not
    already exist and is never removed on failure, preserving forensic evidence.
    """
    parent_generation = Path(parent_generation).resolve(strict=True)
    gtfs_zip = Path(gtfs_zip).resolve(strict=True)
    output_generation = Path(output_generation).resolve()
    if output_generation.exists():
        raise FileExistsError(output_generation)
    if output_generation == parent_generation or parent_generation in output_generation.parents:
        raise ValueError("Output generation must be outside the sealed parent")

    parent_manifest = _read_manifest(parent_generation)
    verify_artifacts(parent_generation)
    parent_store = ReferenceStore(
        parent_generation / "reference.sqlite", parent_manifest["generationId"]
    )
    expected_source = (
        parent_manifest["inputs"].get("israel-public-transportation.zip", {}).get("sha256")
    )
    if not expected_source or parent_store.metadata.source_sha256 != expected_source:
        raise ValueError("Parent reference does not match its sealed GTFS input hash")
    rows, member_sha256 = _parse_source(gtfs_zip, expected_source)

    identity = dict(parent_manifest["identity"])
    identity["parserVersion"] = PARSER_VERSION
    generation_id = _generation_id(identity)
    if generation_id == parent_manifest["generationId"]:
        raise ValueError("Parser version did not produce a new generation identity")

    output_generation.parent.mkdir(parents=True, exist_ok=True)
    output_generation.mkdir(exist_ok=False)
    started_at = datetime.now(UTC).isoformat()
    provenance_path = output_generation / "translation-repair.json"
    provenance: dict[str, Any] = {
        "state": "repairing",
        "policy": REPAIR_POLICY,
        "startedAt": started_at,
        "parentGenerationPath": str(parent_generation),
        "parentGenerationId": parent_manifest["generationId"],
        "parentReferenceSha256": parent_manifest["artifacts"]["reference"]["sha256"],
        "gtfsSourcePath": str(gtfs_zip),
        "gtfsSourceSha256": expected_source,
        "translationsMember": "translations.txt",
        "translationsMemberSha256": member_sha256,
        "rowCount": len(rows),
        "conflicts": 0,
        "outputGenerationId": generation_id,
    }
    # Create evidence before the expensive copy; failure remains explicit.
    _json_write(provenance_path, provenance)
    try:
        shutil.copytree(
            parent_generation,
            output_generation,
            dirs_exist_ok=True,
            copy_function=shutil.copy2,
        )
        output_manifest_path = output_generation / "manifest.json"
        output_manifest = json.loads(output_manifest_path.read_text(encoding="utf-8"))
        output_manifest["state"] = "repairing"
        output_manifest["identity"] = identity
        output_manifest["parserVersion"] = PARSER_VERSION
        output_manifest["generationId"] = generation_id
        output_manifest_path.write_text(
            json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        content_hash, row_count, prior_counts = _repair_database(
            output_generation / "reference.sqlite", rows, generation_id, expected_source
        )
        reference_metadata = ReferenceStore(
            output_generation / "reference.sqlite", generation_id
        ).metadata
        output_manifest["artifacts"]["reference"].update(
            {
                "path": "reference.sqlite",
                "sha256": file_sha256(output_generation / "reference.sqlite"),
                "contentSha256": content_hash,
                "counts": reference_metadata.counts,
            }
        )
        output_manifest["artifacts"]["reference"].pop("reusedFrom", None)
        output_manifest["state"] = "building"
        (output_generation / "manifest.json").write_text(
            json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        # Verify every immutable output artifact before sealing ready.
        verify_artifacts(output_generation)
        ReferenceStore(output_generation / "reference.sqlite", generation_id)
        output_manifest["state"] = "ready"
        output_manifest["builtAt"] = datetime.now(UTC).isoformat()
        (output_generation / "manifest.json").write_text(
            json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        verify_artifacts(output_generation)
        provenance.update(
            {
                "state": "ready",
                "finishedAt": datetime.now(UTC).isoformat(),
                "outputReferenceSha256": output_manifest["artifacts"]["reference"]["sha256"],
                "outputContentSha256": content_hash,
                "previousCounts": prior_counts,
                "counts": reference_metadata.counts,
                "repairedRows": row_count,
                "freshnessRenewed": False,
            }
        )
        provenance_path.unlink()
        _json_write(provenance_path, provenance)
        return output_generation
    except Exception as exc:
        manifest_path = output_generation / "manifest.json"
        if manifest_path.exists():
            try:
                failed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                failed_manifest["state"] = "failed"
                failed_manifest["failure"] = f"{type(exc).__name__}: {exc}"
                manifest_path.write_text(
                    json.dumps(failed_manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError, json.JSONDecodeError:
                pass
        provenance.update(
            {
                "state": "failed",
                "finishedAt": datetime.now(UTC).isoformat(),
                "errorType": type(exc).__name__,
                "error": str(exc),
            }
        )
        provenance_path.unlink(missing_ok=True)
        _json_write(provenance_path, provenance)
        raise
