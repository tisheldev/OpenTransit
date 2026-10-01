"""Independent geocoder backends run concurrently without changing merged output."""

import asyncio
import time
from types import SimpleNamespace

import pytest

import opentransit.geocoding as geocoding
from opentransit.photon_geocoder import PhotonUnavailable


def _snapshot():
    return SimpleNamespace(
        generation=SimpleNamespace(id="test-generation"),
        address_provider=object(),
        address_provider_required=False,
    )


def _slow_backends(monkeypatch, *, photon_delay, motis_delay, events):
    class SlowPhoton:
        def __init__(self, *_args):
            pass

        async def search(self, *_args, **_kwargs):
            events.append("photon-start")
            await asyncio.sleep(photon_delay)
            events.append("photon-end")
            return SimpleNamespace(items=[{"kind": "address", "order": 1}])

    async def motis(snapshot, query, **kwargs):
        events.append("motis-start")
        await asyncio.sleep(motis_delay)
        events.append("motis-end")
        return SimpleNamespace(items=[{"kind": "poi", "order": 2}], searched_types=("poi",))

    monkeypatch.setattr(geocoding, "PhotonGeocoder", SlowPhoton)
    monkeypatch.setattr(geocoding, "geocode_with_motis", motis)


def test_photon_and_motis_take_the_slower_backend_not_the_sum(monkeypatch):
    delay = 0.3
    events = []
    _slow_backends(monkeypatch, photon_delay=delay, motis_delay=delay, events=events)

    async def run():
        started = time.perf_counter()
        result = await geocoding.geocode_places(
            _snapshot(), "Example Place", types=("poi", "address")
        )
        return result, time.perf_counter() - started

    result, elapsed = asyncio.run(run())
    # Sequential execution needs two full delays; concurrency needs about one.
    assert elapsed < 1.6 * delay
    # Both requests were in flight before either finished.
    assert sorted(events[:2]) == ["motis-start", "photon-start"]
    assert [item["kind"] for item in result.items] == ["address", "poi"]
    assert result.searched_types == ("poi", "address")
    assert result.unavailable_types == ()


def test_merge_order_does_not_depend_on_which_backend_finishes_first(monkeypatch):
    outcomes = []
    for photon_delay, motis_delay in ((0.01, 0.15), (0.15, 0.01)):
        events = []
        _slow_backends(
            monkeypatch, photon_delay=photon_delay, motis_delay=motis_delay, events=events
        )
        result = asyncio.run(
            geocoding.geocode_places(_snapshot(), "Example Place", types=("poi", "address"))
        )
        finished_first = next(event for event in events if event.endswith("-end"))
        outcomes.append((finished_first, result))
    assert outcomes[0][0] == "photon-end"
    assert outcomes[1][0] == "motis-end"
    assert outcomes[0][1] == outcomes[1][1]
    assert [item["kind"] for item in outcomes[0][1].items] == ["address", "poi"]


def test_a_slow_failing_backend_is_unavailable_without_losing_the_other(monkeypatch):
    class FailingPhoton:
        def __init__(self, *_args):
            pass

        async def search(self, *_args, **_kwargs):
            await asyncio.sleep(0.05)
            raise PhotonUnavailable("timed out")

    async def motis(snapshot, query, **kwargs):
        await asyncio.sleep(0.01)
        return SimpleNamespace(items=[{"kind": "poi"}], searched_types=("poi",))

    monkeypatch.setattr(geocoding, "PhotonGeocoder", FailingPhoton)
    monkeypatch.setattr(geocoding, "geocode_with_motis", motis)
    result = asyncio.run(
        geocoding.geocode_places(_snapshot(), "Example Place", types=("poi", "address"))
    )
    assert result.unavailable_types == ("address",)
    assert result.searched_types == ("poi",)
    assert result.items == [{"kind": "poi"}]


def test_invalid_address_request_still_raises_while_poi_search_is_in_flight(monkeypatch):
    class RejectingPhoton:
        def __init__(self, *_args):
            pass

        async def search(self, *_args, **_kwargs):
            raise ValueError("invalid request")

    async def motis(snapshot, query, **kwargs):
        await asyncio.sleep(0.01)
        return SimpleNamespace(items=[{"kind": "poi"}], searched_types=("poi",))

    monkeypatch.setattr(geocoding, "PhotonGeocoder", RejectingPhoton)
    monkeypatch.setattr(geocoding, "geocode_with_motis", motis)
    with pytest.raises(ValueError):
        asyncio.run(
            geocoding.geocode_places(_snapshot(), "Example Place", types=("poi", "address"))
        )
