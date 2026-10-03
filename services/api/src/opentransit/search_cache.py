"""Bounded in-process caches for place-search results (stop search and geocoders).

Every cache here is owned by one generation's object and dies with it:

* the stop-search cache lives on the generation's search index, which is itself bound
  to the snapshot's reference store;
* the geocoder caches are registered against the ``RuntimeSnapshot`` and carry its
  generation ID in every key.

Activating a new generation publishes a new snapshot, so it starts with empty caches
and the retired snapshot's caches are released with it. Values are copied on the way in
and on the way out, so a caller that edits a result never edits the cache.
"""

from __future__ import annotations

import threading
import weakref
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any

# Complete stop-search results (at most 20 items each). About 10-20 KB per entry.
STOP_RESULT_CACHE_ENTRIES = 512
# Complete geocoder responses per backend and snapshot. About 10-30 KB per entry.
GEOCODER_CACHE_ENTRIES = 256


def clone(value: Any) -> Any:
    """Copy of the JSON-like structure results are made of (dicts, lists, tuples, scalars)."""
    if isinstance(value, dict):
        return {key: clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clone(item) for item in value]
    if isinstance(value, tuple):
        return tuple(clone(item) for item in value)
    return value


class ResultCache:
    """Thread-safe LRU of complete results; hits and stores are defensive copies."""

    def __init__(self, max_entries: int) -> None:
        if max_entries < 1:
            raise ValueError("A result cache needs room for at least one entry")
        self.max_entries = max_entries
        self._entries: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            stored = self._entries.get(key)
            if stored is None:
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
        return clone(stored)

    def put(self, key: Hashable, value: Any) -> None:
        stored = clone(value)
        with self._lock:
            self._entries[key] = stored
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


class GeocoderCaches:
    """Per-snapshot geocoder result caches, one per backend, keyed by generation ID."""

    BACKENDS = ("photon", "motis")

    def __init__(self, generation_id: str, max_entries: int = GEOCODER_CACHE_ENTRIES) -> None:
        self.generation_id = generation_id
        self._caches = {backend: ResultCache(max_entries) for backend in self.BACKENDS}

    def get(self, backend: str, key: tuple) -> list[dict[str, Any]] | None:
        return self._caches[backend].get((self.generation_id, *key))

    def put(self, backend: str, key: tuple, items: list[dict[str, Any]]) -> None:
        self._caches[backend].put((self.generation_id, *key), items)

    def clear(self, backend: str) -> None:
        self._caches[backend].clear()

    def size(self, backend: str) -> int:
        return len(self._caches[backend])


_REGISTRY: dict[int, tuple[weakref.ref, GeocoderCaches]] = {}
# Reentrant: a garbage-collection callback may run on a thread that already holds it.
_REGISTRY_LOCK = threading.RLock()


def geocoder_caches(snapshot: Any) -> GeocoderCaches | None:
    """The snapshot's geocoder caches, or None when it has no generation or cannot be tracked.

    Registered by object identity and released when the snapshot is garbage collected,
    so a retired generation's results cannot outlive it or reach another snapshot.
    """
    generation_id = getattr(getattr(snapshot, "generation", None), "id", None)
    if not isinstance(generation_id, str) or not generation_id:
        return None
    key = id(snapshot)
    with _REGISTRY_LOCK:
        entry = _REGISTRY.get(key)
        if entry is not None and entry[0]() is snapshot:
            return entry[1]
        try:
            reference = weakref.ref(snapshot, lambda ref, key=key: _release(key, ref))
        except TypeError:
            return None
        caches = GeocoderCaches(generation_id)
        _REGISTRY[key] = (reference, caches)
        return caches


def _release(key: int, reference: weakref.ref) -> None:
    with _REGISTRY_LOCK:
        entry = _REGISTRY.get(key)
        if entry is not None and entry[0] is reference:
            del _REGISTRY[key]
