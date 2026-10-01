"""Aggregate observed calls into delay and segment run-time distributions.

Keys are route × stop (delay) and route × consecutive stop pair (run time), each by local hour of
the scheduled time and Israeli day type. Every figure carries its sample size; consumers must not
show a figure below their own minimum sample.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime

from opentransit.core.time import JERUSALEM
from opentransit.history.arrivals import ObservedCall


def day_type(day: date) -> str:
    """Israeli service week: Sunday–Thursday weekday, then Friday and Saturday."""
    return {4: "friday", 5: "saturday"}.get(day.weekday(), "weekday")


def local_hour(epoch_seconds: int) -> int:
    return datetime.fromtimestamp(epoch_seconds, JERUSALEM).hour


def percentile(values: list[float], share: float) -> float:
    """Linear-interpolated percentile of a non-empty list (share in [0, 1])."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * share
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summary(values: list[float]) -> dict:
    return {
        "n": len(values),
        "p10": round(percentile(values, 0.1), 1),
        "p50": round(percentile(values, 0.5), 1),
        "p90": round(percentile(values, 0.9), 1),
    }


def labelled(stats: dict, prefix: str) -> dict:
    """{"n", "p10", ...} → {"samples", "<prefix>P10Seconds", ...}."""
    return {"samples": stats["n"]} | {
        f"{prefix}{key.upper()}Seconds": value for key, value in stats.items() if key != "n"
    }


class Accumulator:
    def __init__(self, kind_of_day: str):
        self.day_type = kind_of_day
        self.delays: dict[tuple, list[float]] = defaultdict(list)
        self.segments: dict[tuple, list[tuple[float, float]]] = defaultdict(list)

    def add(self, route_id: str, calls: list[ObservedCall]) -> None:
        for call in calls:
            if call.observed is not None:
                key = (route_id, call.stop_id, local_hour(call.scheduled))
                self.delays[key].append(call.observed - call.scheduled)
        for first, second in zip(calls, calls[1:], strict=False):
            if first.observed is None or second.observed is None:
                continue
            scheduled = second.scheduled - first.scheduled
            key = (route_id, first.stop_id, second.stop_id, local_hour(first.scheduled))
            self.segments[key].append((second.observed - first.observed, scheduled))

    def delay_rows(self) -> list[dict]:
        return [
            {
                "routeId": route,
                "stopId": stop,
                "hour": hour,
                "dayType": self.day_type,
                **labelled(summary(values), "delay"),
            }
            for (route, stop, hour), values in sorted(self.delays.items())
        ]

    def segment_rows(self) -> list[dict]:
        rows = []
        for (route, origin, destination, hour), samples in sorted(self.segments.items()):
            actual = [run for run, _ in samples]
            scheduled = [planned for _, planned in samples]
            rows.append(
                {
                    "routeId": route,
                    "fromStopId": origin,
                    "toStopId": destination,
                    "hour": hour,
                    "dayType": self.day_type,
                    "scheduledSecondsMedian": percentile(scheduled, 0.5),
                    **labelled(summary(actual), "run"),
                }
            )
        return rows
