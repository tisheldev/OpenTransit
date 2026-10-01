import asyncio
from types import SimpleNamespace

import pytest

import opentransit.geocoding as geocoding
from opentransit.motis_geocoder import GeocoderUnavailable
from opentransit.photon_geocoder import PhotonUnavailable


def _snapshot(*, provider=None, required=False):
    return SimpleNamespace(
        generation=SimpleNamespace(id="test-generation"),
        address_provider=provider,
        address_provider_required=required,
    )


def test_legacy_snapshot_without_declared_photon_provider_uses_motis_for_both(monkeypatch):
    calls = []

    async def motis(snapshot, query, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            items=[{"kind": "poi"}, {"kind": "address"}], searched_types=kwargs["types"]
        )

    monkeypatch.setattr(geocoding, "geocode_with_motis", motis)
    result = asyncio.run(
        geocoding.geocode_places(
            _snapshot(), "Example Place", types=("poi", "address"), request_id="ab" * 16
        )
    )
    assert calls[0]["types"] == ("poi", "address")
    assert calls[0]["request_id"] == "ab" * 16
    assert [item["kind"] for item in result.items] == ["poi", "address"]
    assert result.unavailable_types == ()


def test_required_missing_photon_address_is_unavailable_without_motis_address_fallback(
    monkeypatch,
):
    calls = []

    async def motis(snapshot, query, **kwargs):
        calls.append(kwargs["types"])
        return SimpleNamespace(items=[{"kind": "poi"}], searched_types=("poi",))

    monkeypatch.setattr(geocoding, "geocode_with_motis", motis)
    result = asyncio.run(
        geocoding.geocode_places(
            _snapshot(required=True), "Example Place", types=("address", "poi")
        )
    )
    assert calls == [("poi",)]
    assert result.searched_types == ("poi",)
    assert result.unavailable_types == ("address",)
    assert result.items == [{"kind": "poi"}]


def test_photon_failure_keeps_successful_poi_results_and_order_is_deterministic(monkeypatch):
    class FailedPhoton:
        def __init__(self, *_args):
            pass

        async def search(self, *_args, **_kwargs):
            raise PhotonUnavailable("fixed sanitized failure")

    async def motis(snapshot, query, **kwargs):
        return SimpleNamespace(items=[{"kind": "poi", "order": 1}], searched_types=("poi",))

    monkeypatch.setattr(geocoding, "PhotonGeocoder", FailedPhoton)
    monkeypatch.setattr(geocoding, "geocode_with_motis", motis)
    result = asyncio.run(
        geocoding.geocode_places(
            _snapshot(provider=object()),
            "Example Place",
            types=("poi", "address"),
        )
    )
    assert result.unavailable_types == ("address",)
    assert result.searched_types == ("poi",)
    assert result.items == [{"kind": "poi", "order": 1}]


def test_photon_and_poi_results_have_stable_category_order(monkeypatch):
    class GoodPhoton:
        def __init__(self, *_args):
            pass

        async def search(self, *_args, **_kwargs):
            return SimpleNamespace(items=[{"kind": "address", "order": 1}])

    async def motis(snapshot, query, **kwargs):
        return SimpleNamespace(items=[{"kind": "poi", "order": 2}], searched_types=("poi",))

    monkeypatch.setattr(geocoding, "PhotonGeocoder", GoodPhoton)
    monkeypatch.setattr(geocoding, "geocode_with_motis", motis)
    result = asyncio.run(
        geocoding.geocode_places(
            _snapshot(provider=object()), "Example Place", types=("poi", "address")
        )
    )
    assert [item["kind"] for item in result.items] == ["address", "poi"]
    assert result.searched_types == ("poi", "address")


def test_all_requested_providers_unavailable_raises_service_error(monkeypatch):
    class FailedPhoton:
        def __init__(self, *_args):
            pass

        async def search(self, *_args, **_kwargs):
            raise PhotonUnavailable("unavailable")

    async def motis(snapshot, query, **kwargs):
        raise GeocoderUnavailable("unavailable")

    monkeypatch.setattr(geocoding, "PhotonGeocoder", FailedPhoton)
    monkeypatch.setattr(geocoding, "geocode_with_motis", motis)
    with pytest.raises(GeocoderUnavailable):
        asyncio.run(
            geocoding.geocode_places(
                _snapshot(provider=object()),
                "Example Place",
                types=("address", "poi"),
            )
        )
