"""Write and pin OB-01 result JSON so its bytes and digests agree on every checkout.

`.gitattributes` stores result files with LF (`text eol=lf`). A result written with the platform
newline (CRLF on Windows) hashes differently from the committed blob, so a digest recorded by a
later result could only be verified on the original Windows working copy. Results are therefore
written with LF only, and a referenced result is pinned by the digest of its LF bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def write_result_json(path: Path, value: dict) -> None:
    """Write `value` as indented UTF-8 JSON with LF newlines; never overwrite a result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    except FileExistsError:
        raise SystemExit(f"refusing to overwrite {path}") from None


def result_sha256(path: Path) -> str:
    """SHA-256 of a JSON result's canonical (LF) bytes, as Git stores the file.

    JSON escapes CR inside strings, so every raw CRLF in a result file is a line ending.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
