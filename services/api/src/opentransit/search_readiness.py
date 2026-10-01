"""Truthful place-search readiness: the stop index and one warm-up per geocoder backend.

A generation is ready to serve passenger searches only when its in-memory stop index
exists and every enabled geocoder backend (the Photon address provider and the MOTIS
place geocoder) has answered one bounded warm-up query. Warm-up runs before a snapshot
is published (startup or activation), so passengers never pay a cold backend. A backend
that stays unavailable keeps the existing honest semantics (its category is reported
unavailable by the search endpoint) and readiness names the reason until a background
retry succeeds.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from opentransit.api.log import LOG
from opentransit.geocoding import geocode_places
from opentransit.stop_search import prepare_search_index, search_index_ready

# Fixed, non-personal warm-up query. It is the only query text any warm-up ever sends
# or logs; results are discarded.
WARMUP_QUERY = "Tel Aviv"
WARMUP_LANGUAGE = "en"

INDEX_BUILDING = "SEARCH_INDEX_BUILDING"
INDEX_UNAVAILABLE = "SEARCH_INDEX_UNAVAILABLE"
WARMING = "warming"
READY = "ready"
UNAVAILABLE = "unavailable"

# backend kind -> (readiness condition, warming reason, unavailable reason)
BACKENDS: dict[str, tuple[str, str, str]] = {
    "address": ("address_search", "ADDRESS_PROVIDER_WARMING", "ADDRESS_PROVIDER_UNAVAILABLE"),
    "poi": ("place_search", "PLACE_PROVIDER_WARMING", "PLACE_PROVIDER_UNAVAILABLE"),
}
MAX_RECORDED_GENERATIONS = 8


@dataclass
class SearchWarmup:
    """Warm-up outcome for one generation, mutated only on the event loop."""

    backends: dict[str, str] = field(default_factory=dict)
    index_failed: bool = False
    retry_task: asyncio.Task | None = None


def enabled_backends(snapshot, motis_geocoding_enabled: bool) -> tuple[str, ...]:
    """Geocoder backends the search endpoint can use for this snapshot, in fixed order."""
    kinds = []
    if getattr(snapshot, "address_provider", None) is not None:
        kinds.append("address")
    if motis_geocoding_enabled:
        kinds.append("poi")
    return tuple(kinds)


def install_warmup(records: dict[str, SearchWarmup], generation_id: str, record: SearchWarmup):
    """Publish a completed warm-up record for a generation (bounded history)."""
    previous = records.pop(generation_id, None)
    if previous is not None and previous is not record and previous.retry_task is not None:
        previous.retry_task.cancel()
    records[generation_id] = record
    while len(records) > MAX_RECORDED_GENERATIONS:
        evicted = records.pop(next(iter(records)))
        if evicted.retry_task is not None:
            evicted.retry_task.cancel()


async def prepare_search(
    snapshot,
    backends,
    *,
    attempts: int,
    retry_seconds: float,
    timeout_seconds: float,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
) -> SearchWarmup:
    """Build the snapshot's stop index, then warm its geocoders; never raises for either.

    Runs before the snapshot is published so a half-built index or a cold backend is
    never visible to requests. Failures are recorded and surface through readiness.
    """
    record = SearchWarmup({kind: WARMING for kind in backends})
    if snapshot.reference is not None:
        try:
            await asyncio.to_thread(prepare_search_index, snapshot.reference)
        except Exception as exc:
            record.index_failed = True
            LOG.warning("search_index_build_failed kind=%s", type(exc).__name__)
    await warm_backends(
        snapshot,
        record,
        attempts=attempts,
        retry_seconds=retry_seconds,
        timeout_seconds=timeout_seconds,
        sleep=sleep,
    )
    return record


def readiness_reasons(snapshot, record: SearchWarmup | None, backends) -> list[dict[str, str]]:
    """Safe reason codes for everything that keeps place search from being ready."""
    reasons: list[dict[str, str]] = []
    if snapshot.reference is not None and not search_index_ready(snapshot.reference):
        failed = record is not None and record.index_failed
        reasons.append(
            {
                "condition": "search_index",
                "reason": INDEX_UNAVAILABLE if failed else INDEX_BUILDING,
            }
        )
    for kind in backends:
        state = record.backends.get(kind, WARMING) if record is not None else WARMING
        if state == READY:
            continue
        condition, warming, unavailable = BACKENDS[kind]
        reasons.append(
            {"condition": condition, "reason": unavailable if state == UNAVAILABLE else warming}
        )
    return reasons


async def _probe(snapshot, kind: str, timeout_seconds: float) -> bool:
    """One bounded fixed-query request; True only when the backend itself answered."""
    try:
        async with asyncio.timeout(timeout_seconds):
            result = await geocode_places(
                snapshot, WARMUP_QUERY, language=WARMUP_LANGUAGE, types=(kind,), limit=1
            )
    except Exception:
        return False
    return kind in result.searched_types and kind not in result.unavailable_types


async def warm_backend(
    snapshot,
    kind: str,
    *,
    attempts: int,
    retry_seconds: float,
    timeout_seconds: float,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
) -> bool:
    for attempt in range(attempts):
        if await _probe(snapshot, kind, timeout_seconds):
            return True
        if attempt + 1 < attempts:
            await sleep(retry_seconds)
    return False


async def warm_backends(
    snapshot,
    record: SearchWarmup,
    *,
    attempts: int,
    retry_seconds: float,
    timeout_seconds: float,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
) -> None:
    """Warm every pending backend concurrently; each ends ready or unavailable."""
    pending = [kind for kind, state in record.backends.items() if state != READY]

    async def one(kind: str) -> None:
        ok = await warm_backend(
            snapshot,
            kind,
            attempts=attempts,
            retry_seconds=retry_seconds,
            timeout_seconds=timeout_seconds,
            sleep=sleep,
        )
        record.backends[kind] = READY if ok else UNAVAILABLE
        if not ok:
            LOG.warning("search_warmup_failed backend=%s", kind)

    await asyncio.gather(*(one(kind) for kind in pending))


async def retry_until_ready(
    snapshot,
    record: SearchWarmup,
    *,
    is_current: Callable[[], bool],
    timeout_seconds: float,
    interval_seconds: float,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
) -> None:
    """Background recovery: probe unavailable backends until ready or the snapshot retires."""
    while any(state != READY for state in record.backends.values()):
        await sleep(interval_seconds)
        if not is_current():
            return
        for kind in [kind for kind, state in record.backends.items() if state != READY]:
            if await _probe(snapshot, kind, timeout_seconds):
                record.backends[kind] = READY
                LOG.info("search_warmup_recovered backend=%s", kind)
