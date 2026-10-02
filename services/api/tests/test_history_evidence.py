"""Result files must hash the same on every checkout (Git stores them with LF)."""

import hashlib
import json
from pathlib import Path

import pytest

from opentransit.history.evidence import result_sha256, write_result_json

RESULTS = Path(__file__).resolve().parents[1] / "results"


def test_write_result_json_writes_utf8_with_lf_only_and_never_overwrites(tmp_path):
    path = tmp_path / "nested" / "result.json"
    value = {"name": "תחנה מרכזית", "rows": [1, 2], "text": "a\r\nb"}

    write_result_json(path, value)

    body = path.read_bytes()
    assert b"\r" not in body  # a CR inside a string is escaped by JSON, never written raw
    assert body.endswith(b"}\n")
    assert json.loads(body.decode("utf-8")) == value
    assert "תחנה" in body.decode("utf-8")  # ensure_ascii=False, UTF-8 on disk
    with pytest.raises(SystemExit):
        write_result_json(path, {"other": True})
    assert path.read_bytes() == body


def test_result_sha256_is_the_digest_of_the_lf_bytes_git_stores(tmp_path):
    lf = b'{\n  "a": 1\n}\n'
    lf_copy, crlf_copy = tmp_path / "lf.json", tmp_path / "crlf.json"
    lf_copy.write_bytes(lf)
    crlf_copy.write_bytes(lf.replace(b"\n", b"\r\n"))  # a Windows autocrlf working copy

    expected = hashlib.sha256(lf).hexdigest()
    assert result_sha256(lf_copy) == expected
    assert result_sha256(crlf_copy) == expected


def committed_bytes(path: Path) -> bytes:
    """The blob Git stores for a `text eol=lf` file, whatever the working copy uses."""
    return path.read_bytes().replace(b"\r\n", b"\n")


@pytest.mark.parametrize(
    ("result", "section", "path_key", "digest_key"),
    [
        ("ob01-heldout-202601-vs-202511-01.json", "calibration", "report", "reportSha256"),
        ("ob01-outlier-review-202511-01.json", None, "monthReport", "monthReportSha256"),
    ],
)
def test_committed_ob01_results_reference_the_committed_month_bytes(
    result, section, path_key, digest_key
):
    record = json.loads((RESULTS / result).read_text(encoding="utf-8"))
    pins = record[section] if section else record
    assert pins[path_key] == "services/api/results/ob01-month-202511-01.json"

    month = RESULTS / "ob01-month-202511-01.json"
    assert pins[digest_key] == hashlib.sha256(committed_bytes(month)).hexdigest()
