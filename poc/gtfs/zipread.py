"""Streaming reader for a GTFS zip.

Two properties matter here and both are non-negotiable:

1. **Nothing is extracted to disk and nothing is read whole.** The 10-day
   feed's `stop_times.txt` is 1.77 GB uncompressed (KDP-003). Members are
   decompressed on the fly through a text wrapper.
2. **Reading a member to EOF verifies its CRC.** Python's ZipExtFile checks
   the stored CRC as the last chunk is consumed, so a full parse pass *is* a
   full integrity check of that member — that is the "zip validation" half of
   the E01 change-detection rule.

Encoding: `utf-8-sig`, strict. The 60-day feed writes a UTF-8 BOM on every
file and the 10-day feed writes none (KDP-005), so a reader that assumes
either one is wrong half the time. Strict errors mean a mis-encoded feed
raises rather than silently substituting U+FFFD into Hebrew names (E03).
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# csv defaults to 128 KB; some GTFS free-text fields are longer than that.
csv.field_size_limit(1 << 24)


@dataclass
class MalformedRow:
    line: int
    expected: int
    actual: int
    raw: str


@dataclass
class ReadStats:
    """Per-member outcome of a streaming pass. Counts, never silent drops."""

    member: str
    rows: int = 0
    malformed: int = 0
    samples: list[MalformedRow] = field(default_factory=list)
    has_bom: bool = False
    header: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "member": self.member,
            "rows": self.rows,
            "malformed_rows": self.malformed,
            "has_utf8_bom": self.has_bom,
            "header": self.header,
            "malformed_samples": [
                {"line": s.line, "expected_fields": s.expected,
                 "actual_fields": s.actual, "raw": s.raw}
                for s in self.samples
            ],
        }


class GtfsZip:
    """A GTFS zip opened for streaming reads."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.zf = zipfile.ZipFile(self.path)
        self._names = {i.filename for i in self.zf.infolist()}

    def close(self) -> None:
        self.zf.close()

    def __enter__(self) -> "GtfsZip":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- inspection -----------------------------------------------------
    def names(self) -> list[str]:
        return sorted(self._names)

    def has(self, member: str) -> bool:
        return member in self._names

    def uncompressed_size(self, member: str) -> int:
        return self.zf.getinfo(member).file_size

    def sizes(self) -> dict[str, int]:
        return {i.filename: i.file_size for i in self.zf.infolist()}

    # -- reading --------------------------------------------------------
    def _text(self, member: str) -> io.TextIOWrapper:
        raw = self.zf.open(member, "r")
        return io.TextIOWrapper(raw, encoding="utf-8-sig", errors="strict", newline="")

    def rows(
        self, member: str, stats: ReadStats | None = None, max_samples: int = 5
    ) -> Iterator[dict[str, str]]:
        """Yield rows as dicts, counting (never dropping) malformed rows.

        A row with more fields than the header keeps its surplus under the
        key `_extra`; a row with fewer is padded with ''. Both are counted.
        TripIdToDate.txt needs exactly this (KDP-007): every one of its
        1.96M rows carries a trailing comma the header does not declare.
        """
        st = stats if stats is not None else ReadStats(member)
        st.member = member
        with self.zf.open(member, "r") as raw:
            head = raw.read(3)
            st.has_bom = head == b"\xef\xbb\xbf"
        with self._text(member) as fh:
            reader = csv.reader(fh)
            try:
                header = next(reader)
            except StopIteration:
                st.header = []
                return
            st.header = header
            width = len(header)
            for row in reader:
                st.rows += 1
                n = len(row)
                if n != width:
                    st.malformed += 1
                    if len(st.samples) < max_samples:
                        st.samples.append(
                            MalformedRow(reader.line_num, width, n, ",".join(row)[:300])
                        )
                    if n < width:
                        row = row + [""] * (width - n)
                    else:
                        extra = row[width:]
                        row = row[:width]
                        rec = dict(zip(header, row))
                        rec["_extra"] = extra  # type: ignore[assignment]
                        yield rec
                        continue
                yield dict(zip(header, row))

    def verify_member_crc(self, member: str, chunk: int = 1 << 20) -> int:
        """Read a member to EOF purely to force its CRC check. Returns bytes."""
        total = 0
        with self.zf.open(member, "r") as fh:
            while True:
                b = fh.read(chunk)
                if not b:
                    break
                total += len(b)
        return total


def validate_zip(path: str | Path, required: list[str] | None = None,
                 crc_limit_bytes: int = 64 << 20) -> dict:
    """Structural validation used by the refresh path (E01).

    Verifies the central directory parses, that required members exist, and
    CRC-checks every member up to `crc_limit_bytes` uncompressed. The huge
    members (stop_times, shapes, translations) are CRC-checked later by the
    parse pass, which reads them to EOF anyway; re-reading 2 GB twice per
    refresh buys nothing.
    """
    out: dict = {"path": str(path), "valid": False, "members": 0,
                 "crc_verified": [], "crc_deferred": [], "missing": []}
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        out["members"] = len(infos)
        names = {i.filename for i in infos}
        for req in required or []:
            if req not in names:
                out["missing"].append(req)
        for i in infos:
            if i.file_size <= crc_limit_bytes:
                with zf.open(i, "r") as fh:
                    while fh.read(1 << 20):
                        pass
                out["crc_verified"].append(i.filename)
            else:
                out["crc_deferred"].append(i.filename)
    out["valid"] = not out["missing"]
    return out
