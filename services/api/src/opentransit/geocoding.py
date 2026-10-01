"""Deterministic orchestration for Photon addresses and MOTIS place search."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from opentransit.motis_geocoder import GeocodeResult, GeocoderUnavailable
from opentransit.motis_geocoder import geocode_places as geocode_with_motis
from opentransit.photon_geocoder import PhotonGeocoder, PhotonUnavailable


@dataclass(frozen=True)
class GeocodingResult:
    items: list[dict[str, Any]]
    searched_types: tuple[str, ...]
    unavailable_types: tuple[str, ...] = ()

    @property
    def outcome(self) -> str:
        return "matches_found" if self.items else "no_match"


async def geocode_places(
    snapshot,
    query: str,
    *,
    language: str = "he",
    near: tuple[float, float] | None = None,
    types: tuple[str, ...] = ("poi", "address"),
    limit: int = 10,
    request_id: str | None = None,
) -> GeocodingResult:
    """Use a declared Photon binding for addresses without changing legacy MOTIS mode."""
    address_provider = getattr(snapshot, "address_provider", None)
    address_required = bool(getattr(snapshot, "address_provider_required", False))
    if address_provider is None and not address_required:
        result = await geocode_with_motis(
            snapshot,
            query,
            language=language,
            near=near,
            types=types,
            limit=limit,
            request_id=request_id,
        )
        return GeocodingResult(result.items, result.searched_types)

    requested = set(types)
    by_kind: dict[str, list[dict[str, Any]]] = {"address": [], "poi": []}
    searched: set[str] = set()
    unavailable: set[str] = set()

    adapter: PhotonGeocoder | None = None
    if "address" in requested:
        if address_provider is None:
            unavailable.add("address")
        else:
            try:
                adapter = PhotonGeocoder(address_provider, snapshot.generation.id)
            except PhotonUnavailable, ValueError:
                unavailable.add("address")

    async def search_address() -> list[dict[str, Any]]:
        result = await adapter.search(
            query,
            language=language,
            near=near,
            limit=limit,
            request_id=request_id,
        )
        return result.items

    async def search_poi() -> GeocodeResult:
        return await geocode_with_motis(
            snapshot,
            query,
            language=language,
            near=near,
            types=("poi",),
            limit=limit,
            request_id=request_id,
        )

    # The backends are independent, so they run concurrently and the slower one
    # bounds latency instead of the sum. Each keeps its own timeout and failure
    # mapping (adapters bound their own requests). Outcomes are combined below in a
    # fixed address-then-poi order, never in completion order.
    address_outcome, poi_outcome = await asyncio.gather(
        search_address() if adapter is not None else _skipped(),
        search_poi() if "poi" in requested else _skipped(),
        return_exceptions=True,
    )

    if adapter is not None:
        if isinstance(address_outcome, PhotonUnavailable):
            unavailable.add("address")
        elif isinstance(address_outcome, BaseException):
            # Invalid requests (ValueError) and cancellation are not backend outages.
            raise address_outcome
        else:
            by_kind["address"] = address_outcome
            searched.add("address")

    if "poi" in requested:
        if isinstance(poi_outcome, GeocoderUnavailable):
            unavailable.add("poi")
        elif isinstance(poi_outcome, BaseException):
            raise poi_outcome
        else:
            by_kind["poi"] = poi_outcome.items
            searched.update(poi_outcome.searched_types)

    if not searched:
        raise GeocoderUnavailable("All requested geocoding categories are unavailable")
    ordered_types = tuple(kind for kind in types if kind in searched)
    ordered_unavailable = tuple(kind for kind in types if kind in unavailable)
    items = [item for kind in ("address", "poi") for item in by_kind[kind]]
    return GeocodingResult(items, ordered_types, ordered_unavailable)


async def _skipped() -> None:
    """Placeholder for a backend that was not requested."""
    return None
