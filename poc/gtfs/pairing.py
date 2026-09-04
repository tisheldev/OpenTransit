"""`TripIdToDate.zip` — parse, and refuse to pair it with the wrong feed.

`TripIdToDate.zip` is a separate download from the GTFS zip and carries no
version, no feed hash and no publication stamp. Nothing in the file says
which GTFS publication it belongs to. Corpus check E05 requires the ingester
to *refuse* a mismatched pair rather than silently use it, so the pairing
evidence has to be derived from content:

* **key overlap** — what fraction of the GTFS feed's trips can actually be
  looked up in TripIdToDate;
* **window overlap** — whether the TripIdToDate FromDate..ToDate range
  intersects the GTFS service window at all.

Key overlap is the decisive one. The MOT 60-day feed writes trip ids as
`<TripId>_<ddmmyy>`, so the join key is the part before the underscore; the
10-day feed writes a bare numeric id that is drawn from a different id space
entirely. `join_key()` encodes exactly that and nothing more.
"""

from __future__ import annotations

import collections
import datetime as dt
from dataclasses import dataclass, field

from .zipread import GtfsZip, ReadStats

MEMBER = "TripIdToDate.txt"

# The MOT writes dd/mm/yyyy HH:MM:SS in this file, unlike the GTFS yyyymmdd.
_DATE_FMT = "%d/%m/%Y %H:%M:%S"


class FeedPairingError(RuntimeError):
    """The TripIdToDate snapshot does not belong with this GTFS snapshot."""


def join_key(trip_id: str) -> str:
    """The id TripIdToDate.TripId is expected to match.

    60-day feed: '584872860_200926' -> '584872860'
    10-day feed: '1684794342'       -> '1684794342'
    """
    return trip_id.split("_", 1)[0]


@dataclass
class TripIdToDate:
    rows: int = 0
    distinct_trip_ids: int = 0
    trip_ids: set[str] = field(default_factory=set)
    min_from_date: dt.date | None = None
    max_to_date: dt.date | None = None
    read_stats: dict = field(default_factory=dict)
    day_in_week: dict[str, int] = field(default_factory=dict)
    records: list[tuple] = field(default_factory=list)


def parse_trip_id_to_date(path, keep_records: bool = False) -> TripIdToDate:
    """Stream the file for counts and the id set.

    `keep_records=False` by default: 1.96M rows are streamed straight into
    Postgres by db.load_trip_id_to_date, never buffered in a list.
    """
    out = TripIdToDate()
    st = ReadStats(MEMBER)
    dow: collections.Counter[str] = collections.Counter()
    with GtfsZip(path) as z:
        if not z.has(MEMBER):
            raise FileNotFoundError(f"{path} has no {MEMBER}")
        for row in z.rows(MEMBER, st):
            tid = row.get("TripId", "")
            out.trip_ids.add(tid)
            dow[row.get("DayInWeek", "")] += 1
            fd = _parse_dt(row.get("FromDate"))
            td = _parse_dt(row.get("ToDate"))
            if fd and (out.min_from_date is None or fd < out.min_from_date):
                out.min_from_date = fd
            if td and (out.max_to_date is None or td > out.max_to_date):
                out.max_to_date = td
            if keep_records:
                out.records.append((
                    row.get("LineDetailRecordId"), row.get("OfficeLineId"),
                    row.get("Direction"), row.get("LineAlternative"),
                    fd, td, tid,
                    _int(row.get("DayInWeek")), row.get("DepartureTime"),
                ))
    out.rows = st.rows
    out.distinct_trip_ids = len(out.trip_ids)
    out.read_stats = st.as_dict()
    out.day_in_week = dict(dow)
    return out


def _parse_dt(s: str | None) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.datetime.strptime(s.strip(), _DATE_FMT).date()
    except ValueError:
        try:
            return dt.datetime.strptime(s.strip(), "%d/%m/%Y").date()
        except ValueError:
            return None


def _int(s: str | None) -> int | None:
    try:
        return int(s) if s not in (None, "") else None
    except ValueError:
        return None


def check_pairing(feed_trip_ids, t2d: TripIdToDate,
                  feed_window: tuple[dt.date | None, dt.date | None] = (None, None),
                  min_overlap: float = 0.50) -> dict:
    """Evidence for E05. Returns a verdict dict; does not raise."""
    keys = {join_key(t) for t in feed_trip_ids}
    matched = keys & t2d.trip_ids
    frac = (len(matched) / len(keys)) if keys else 0.0

    fs, fe = feed_window
    window_overlap = None
    if fs and fe and t2d.min_from_date and t2d.max_to_date:
        window_overlap = not (t2d.max_to_date < fs or t2d.min_from_date > fe)

    return {
        "feed_distinct_trip_ids": len(feed_trip_ids),
        "feed_distinct_join_keys": len(keys),
        "trip_id_to_date_distinct_ids": t2d.distinct_trip_ids,
        "matched_join_keys": len(matched),
        "match_fraction": round(frac, 6),
        "min_overlap_required": min_overlap,
        "trip_id_to_date_window": [
            t2d.min_from_date.isoformat() if t2d.min_from_date else None,
            t2d.max_to_date.isoformat() if t2d.max_to_date else None,
        ],
        "feed_service_window": [fs.isoformat() if fs else None,
                                fe.isoformat() if fe else None],
        "date_windows_overlap": window_overlap,
        "verdict": "ACCEPTED" if frac >= min_overlap else "REJECTED",
    }


def pair_or_raise(feed_trip_ids, t2d: TripIdToDate,
                  feed_window=(None, None), min_overlap: float = 0.50,
                  allow_unpaired: bool = False) -> dict:
    """Default behaviour on a mismatch is to stop, per E05."""
    result = check_pairing(feed_trip_ids, t2d, feed_window, min_overlap)
    if result["verdict"] == "REJECTED" and not allow_unpaired:
        raise FeedPairingError(
            "TripIdToDate does not belong with this GTFS snapshot: only "
            f"{result['matched_join_keys']} of {result['feed_distinct_join_keys']} "
            f"feed trip ids ({result['match_fraction']:.4%}) are present in "
            f"{MEMBER}, below the {min_overlap:.0%} threshold. Refusing to pair."
        )
    return result
