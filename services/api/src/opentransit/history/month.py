"""Multi-day OB-01 batch: per-day observation files, month tables and a held-out check.

Stage 1 (`observe_day`) writes every scheduled call of one service day — observed or not, with
the reason — into route-hashed bucket files, so stage 2 (`MonthAggregate`) can build month
distributions one bucket at a time in bounded memory, and coverage (observed ÷ scheduled calls)
is known for every figure. Stage 3 (`HeldOutCheck`) scores a held-out period against the
calibration table: if the distributions transfer, about 10% of held-out observations fall below
the calibration p10, 50% below p50 and 10% above p90.

Publication rule (OB-01 "coverage published beside every figure"): a figure is publishable only
with at least `MIN_SAMPLES` observations on at least `MIN_SERVICE_DAYS` distinct service days
and coverage of at least `MIN_COVERAGE`; otherwise consumers show no figure. Figures stay
historical and are not shown publicly before Phase 4 and data terms.
"""

from __future__ import annotations

import csv
import gzip
import random
import zlib
from array import array
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from opentransit.history.arrivals import clean_track, observe_calls
from opentransit.history.distributions import local_hour, percentile, summary
from opentransit.history.schedule import DaySchedule, match_ride
from opentransit.history.siri_archive import Ride

BUCKETS = 16
MIN_SAMPLES = 20
MIN_SERVICE_DAYS = 4
MIN_COVERAGE = 0.5
ERROR_BIN_S = 10  # absolute-error histogram resolution (inference is about ±30 s)
HISTOGRAM_BIN_S = 10
FIELDS = ("trip", "route", "seq", "stop", "scheduled", "delay", "bracket", "reason")

Row = tuple[str, str, int, str, int, int | None, int | None, str]


def bucket_of(route_id: str) -> int:
    return zlib.crc32(route_id.encode()) % BUCKETS


def publishable(samples: int, service_days: int, coverage: float) -> bool:
    return samples >= MIN_SAMPLES and service_days >= MIN_SERVICE_DAYS and coverage >= MIN_COVERAGE


class DayWriter:
    """Gzipped CSV per route bucket for one service day."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.streams = [
            gzip.open(directory / f"calls-{index:02d}.csv.gz", "wt", encoding="utf-8", newline="")
            for index in range(BUCKETS)
        ]
        self.writers = [csv.writer(stream) for stream in self.streams]
        for writer in self.writers:
            writer.writerow(FIELDS)

    def write(self, row: Row) -> None:
        self.writers[bucket_of(row[1])].writerow(row)

    def close(self) -> None:
        for stream in self.streams:
            stream.close()


def read_bucket(directory: Path, bucket: int) -> Iterator[Row]:
    with gzip.open(directory / f"calls-{bucket:02d}.csv.gz", "rt", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        next(reader)
        for trip, route, seq, stop, scheduled, delay, bracket, reason in reader:
            yield (
                trip,
                route,
                int(seq),
                stop,
                int(scheduled),
                int(delay) if delay else None,
                int(bracket) if bracket else None,
                reason,
            )


def observe_day(
    schedule: DaySchedule,
    rides: dict[str, Ride],
    sink: Callable[[Row], None],
    *,
    decimation_share: float = 0.0,
    seed: int = 20261002,
) -> dict:
    """Match rides to trips, infer stop times and emit one row per scheduled call."""
    reasons: Counter = Counter()
    call_reasons: Counter = Counter()
    tracks: Counter = Counter()
    best: dict[str, tuple[Ride, int]] = {}  # trip_id → (ride, unique pings)
    for ride in rides.values():
        trip, reason = match_ride(schedule, ride.line_ref, ride.origin_departure)
        unique = len(set(ride.at))
        if trip is None:
            reasons[reason] += 1
            if unique < 3:
                reasons[reason + "FewerThan3Pings"] += 1
            continue
        reasons["matched"] += 1
        if trip.trip_id.split("_", 1)[0] == ride.trip_ref:
            reasons["matchedTripRefIsGtfsPrefix"] += 1
        if trip.trip_id in best:
            reasons["extraRideForSameTripDropped"] += 1
            if best[trip.trip_id][1] >= unique:
                continue
        best[trip.trip_id] = (ride, unique)
    rng = random.Random(seed)
    decimation: list[float] = []
    by_agency: dict[str, Counter] = {}
    for trip in schedule.trips.values():
        calls = trip.calls
        if not calls:
            continue
        agency = schedule.routes.get(trip.route_id, {}).get("agency_id", "?")
        counts = by_agency.setdefault(agency, Counter())
        counts["scheduledTrips"] += 1
        counts["scheduledCalls"] += len(calls)
        chosen = best.get(trip.trip_id)
        if chosen is None:
            for call in calls:
                sink(
                    (
                        trip.trip_id,
                        trip.route_id,
                        call.sequence,
                        call.stop_id,
                        call.arrival if call is not calls[0] else call.departure,
                        None,
                        None,
                        "tripNotObserved",
                    )
                )
            call_reasons["tripNotObserved"] += len(calls)
            continue
        ride = chosen[0]
        track, stats = clean_track(ride.points)
        tracks.update(
            pings=stats.pings,
            duplicates=ride.duplicates,
            backwards=stats.backwards,
            speedOutliers=stats.speed_outliers,
        )
        if len(ride.vehicles) > 1:
            tracks["ridesWithSeveralVehicles"] += 1
        observed = observe_calls(track, calls)
        counts["observedTrips"] += 1
        for call in observed:
            delay = None if call.observed is None else call.observed - call.scheduled
            call_reasons[call.reason or "observed"] += 1
            if delay is not None:
                counts["observedCalls"] += 1
            sink(
                (
                    trip.trip_id,
                    trip.route_id,
                    call.sequence,
                    call.stop_id,
                    call.scheduled,
                    delay,
                    call.bracket_s,
                    call.reason or "",
                )
            )
        if decimation_share and len(track) >= 20 and rng.random() < decimation_share:
            for full, thin in zip(observed, observe_calls(track[::2], calls), strict=True):
                if full.observed is not None and thin.observed is not None:
                    decimation.append(abs(thin.observed - full.observed))
    return {
        "matching": {
            "rides": len(rides),
            "outcomes": dict(reasons),
            "scheduledTrips": len(schedule.trips),
            "scheduledTripsObserved": len(best),
            "scheduledTripCoverage": round(len(best) / len(schedule.trips), 4)
            if schedule.trips
            else None,
        },
        "calls": dict(call_reasons),
        "tracks": dict(tracks),
        "interpolationCheckAbsErrorSeconds": summary(decimation) if decimation else None,
        "byAgency": {agency: dict(counts) for agency, counts in sorted(by_agency.items())},
    }


def histogram_summary(histogram: Counter, width: int = HISTOGRAM_BIN_S) -> dict:
    """n, p10, p50, p90 from a histogram of `value // width` bins (bin centres)."""
    total = sum(histogram.values())
    result: dict = {"n": total}
    ordered = sorted(histogram)
    for share, label in ((0.1, "p10"), (0.5, "p50"), (0.9, "p90")):
        seen = 0
        for index in ordered:
            seen += histogram[index]
            if seen >= share * total:
                result[label] = (index + 0.5) * width
                break
    return result


class _Key:
    __slots__ = ("scheduled", "values", "planned", "days")

    def __init__(self) -> None:
        self.scheduled = 0
        self.values = array("i")
        self.planned = array("i")  # scheduled run time per sample (segments only)
        self.days = 0  # bitmask of service-day indices with an observation


def trips_of(rows: Iterable[Row]) -> Iterator[list[Row]]:
    """Group consecutive rows of one trip (files are written trip by trip)."""
    current: list[Row] = []
    for row in rows:
        if current and row[0] != current[0][0]:
            yield current
            current = []
        current.append(row)
    if current:
        yield current


class MonthAggregate:
    """Route × stop delays and route × stop-pair run times by local hour and day type."""

    def __init__(self) -> None:
        self.delays: dict[tuple, _Key] = {}
        self.segments: dict[tuple, _Key] = {}
        self.hourly: dict[tuple[str, int], Counter] = {}  # en-route delay histograms
        self._hours: dict[int, int] = {}

    def _hour(self, epoch_seconds: int) -> int:
        slot = epoch_seconds // 3600  # Israeli offsets are whole hours
        hour = self._hours.get(slot)
        if hour is None:
            hour = self._hours[slot] = local_hour(slot * 3600)
        return hour

    def add(self, day_index: int, kind_of_day: str, rows: Iterable[Row]) -> None:
        bit = 1 << day_index
        hour_of = self._hour
        for trip in trips_of(rows):
            trip.sort(key=lambda row: row[2])
            for position, row in enumerate(trip):
                hour = hour_of(row[4])
                key = (row[1], row[3], hour, kind_of_day)
                stats = self.delays.get(key) or self.delays.setdefault(key, _Key())
                stats.scheduled += 1
                if row[5] is not None:
                    stats.values.append(row[5])
                    stats.days |= bit
                    if position:
                        histogram = self.hourly.setdefault((kind_of_day, hour), Counter())
                        histogram[row[5] // HISTOGRAM_BIN_S] += 1
            for first, second in zip(trip, trip[1:], strict=False):
                key = (first[1], first[3], second[3], hour_of(first[4]), kind_of_day)
                stats = self.segments.get(key) or self.segments.setdefault(key, _Key())
                stats.scheduled += 1
                if first[5] is not None and second[5] is not None:
                    planned = second[4] - first[4]
                    stats.values.append(planned + second[5] - first[5])
                    stats.planned.append(planned)
                    stats.days |= bit

    @staticmethod
    def _figures(stats: _Key, prefix: str) -> dict:
        samples = len(stats.values)
        coverage = round(samples / stats.scheduled, 3) if stats.scheduled else 0.0
        days = stats.days.bit_count()
        values = list(stats.values)
        figures = {
            "scheduledCalls": stats.scheduled,
            "samples": samples,
            "coverage": coverage,
            "serviceDays": days,
        }
        for share, label in ((0.1, "P10"), (0.5, "P50"), (0.9, "P90")):
            figures[f"{prefix}{label}Seconds"] = (
                round(percentile(values, share), 1) if values else None
            )
        figures["publishable"] = publishable(samples, days, coverage)
        return figures

    def hourly_rows(self) -> dict[str, dict[str, dict]]:
        """En-route stop delay (origin excluded) by day type and local hour, all keys pooled."""
        result: dict[str, dict[str, dict]] = {}
        for (kind, hour), histogram in sorted(self.hourly.items()):
            result.setdefault(kind, {})[str(hour)] = histogram_summary(histogram)
        return result

    def delay_rows(self) -> list[dict]:
        return [
            {"routeId": route, "stopId": stop, "hour": hour, "dayType": kind}
            | self._figures(stats, "delay")
            for (route, stop, hour, kind), stats in sorted(self.delays.items())
        ]

    def segment_rows(self) -> list[dict]:
        rows = []
        for (route, origin, destination, hour, kind), stats in sorted(self.segments.items()):
            figures = self._figures(stats, "run")
            figures["scheduledCalls"] = stats.scheduled
            rows.append(
                {
                    "routeId": route,
                    "fromStopId": origin,
                    "toStopId": destination,
                    "hour": hour,
                    "dayType": kind,
                    "scheduledSecondsMedian": percentile(list(stats.planned), 0.5)
                    if stats.planned
                    else None,
                }
                | figures
            )
        return rows


class _Band:
    __slots__ = ("n", "below10", "below50", "above90", "errors_calibration", "errors_schedule")

    def __init__(self) -> None:
        self.n = self.below10 = self.below50 = self.above90 = 0
        self.errors_calibration: Counter = Counter()
        self.errors_schedule: Counter = Counter()

    def add(self, value: float, figures: dict, baseline: float) -> None:
        self.n += 1
        self.below10 += value < figures["p10"]
        self.below50 += value < figures["p50"]
        self.above90 += value > figures["p90"]
        self.errors_calibration[int(abs(value - figures["p50"]) // ERROR_BIN_S)] += 1
        self.errors_schedule[int(abs(value - baseline) // ERROR_BIN_S)] += 1

    @staticmethod
    def _median(histogram: Counter) -> float | None:
        total = sum(histogram.values())
        if not total:
            return None
        seen = 0
        for index in sorted(histogram):
            seen += histogram[index]
            if seen * 2 >= total:
                return (index + 0.5) * ERROR_BIN_S
        raise AssertionError("unreachable")

    def report(self) -> dict:
        if not self.n:
            return {"observations": 0}
        return {
            "observations": self.n,
            "belowP10": round(self.below10 / self.n, 3),
            "belowP50": round(self.below50 / self.n, 3),
            "aboveP90": round(self.above90 / self.n, 3),
            "withinP10P90": round(1 - (self.below10 + self.above90) / self.n, 3),
            "medianAbsErrorSeconds": {
                "calibrationP50": self._median(self.errors_calibration),
                "schedule": self._median(self.errors_schedule),
            },
        }


def hour_band(hour: int) -> str:
    if 6 <= hour < 9:
        return "morningPeak06to09"
    if 15 <= hour < 19:
        return "eveningPeak15to19"
    if 9 <= hour < 15:
        return "midday09to15"
    return "offPeak"


def sample_band(samples: int) -> str:
    for low, high in ((5, 19), (20, 49), (50, 99)):
        if low <= samples <= high:
            return f"samples{low}to{high}"
    return "samples100plus" if samples >= 100 else "samplesUnder5"


class HeldOutCheck:
    """Score held-out observations against calibration figures for the same key.

    `calibration` maps a key (whose third element is the hour and last the day type) to
    {"p10", "p50", "p90", "samples", "publishable"}; `baseline(key, scheduled)` is the
    schedule-only prediction (0 s delay, or the scheduled run time for a segment).
    """

    def __init__(self, calibration: dict, baseline: Callable[[tuple, int], float]):
        self.calibration = calibration
        self.baseline = baseline
        self.missing = 0
        self.bands: dict[str, dict[str, _Band]] = {}
        self.held_out: dict[tuple, list[float]] = {}
        self.shifts: list[float] = []  # |held-out p50 - calibration p50| per well-sampled key

    def _band(self, group: str, label: str) -> _Band:
        return self.bands.setdefault(group, {}).setdefault(label, _Band())

    def add(self, key: tuple, value: float, *, scheduled: int) -> None:
        figures = self.calibration.get(key)
        if figures is None or figures["p50"] is None:
            self.missing += 1
            return
        baseline = self.baseline(key, scheduled)
        status = "publishable" if figures["publishable"] else "notPublishable"
        self._band("byStratum", status).add(value, figures, baseline)
        self._band("bySampleBand", sample_band(figures["samples"])).add(value, figures, baseline)
        if figures["publishable"]:
            self._band("byDayType", key[-1]).add(value, figures, baseline)
            self._band("byHourBand", hour_band(key[-2])).add(value, figures, baseline)
            self.held_out.setdefault(key, []).append(value)

    def settle_keys(self, minimum: int = MIN_SAMPLES) -> None:
        """Turn per-key held-out values into median shifts and drop the values."""
        for key, values in self.held_out.items():
            if len(values) >= minimum:
                self.shifts.append(abs(percentile(values, 0.5) - self.calibration[key]["p50"]))
        self.held_out.clear()

    def merge_into(self, other: HeldOutCheck) -> None:
        """Fold this (per-bucket) check into `other`."""
        self.settle_keys()
        other.missing += self.missing
        other.shifts.extend(self.shifts)
        for group, labels in self.bands.items():
            for label, band in labels.items():
                target = other._band(group, label)
                target.n += band.n
                target.below10 += band.below10
                target.below50 += band.below50
                target.above90 += band.above90
                target.errors_calibration.update(band.errors_calibration)
                target.errors_schedule.update(band.errors_schedule)

    def _shift_summary(self) -> dict | None:
        self.settle_keys()
        return (
            (summary(self.shifts) | {"minimumHeldOutSamples": MIN_SAMPLES}) if self.shifts else None
        )

    def report(self) -> dict:
        return {
            "observationsWithoutCalibrationKey": self.missing,
            **{
                group: {label: band.report() for label, band in sorted(labels.items())}
                for group, labels in sorted(self.bands.items())
            },
            "publishableKeyMedianShiftSeconds": self._shift_summary(),
        }
