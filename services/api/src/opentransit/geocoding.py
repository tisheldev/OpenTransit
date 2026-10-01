"""Deterministic orchestration for Photon addresses and MOTIS place search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opentransit.motis_geocoder import GeocoderUnavailable
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

    if "address" in requested:
        if address_provider is None:
            unavailable.add("address")
        else:
            try:
                adapter = PhotonGeocoder(address_provider, snapshot.generation.id)
            except PhotonUnavailable, ValueError:
                unavailable.add("address")
            else:
                try:
                    result = await adapter.search(
                        query,
                        language=language,
                        near=near,
                        limit=limit,
                        request_id=request_id,
                    )
                    by_kind["address"] = result.items
                    searched.add("address")
                except PhotonUnavailable:
                    unavailable.add("address")
                except ValueError:
                    raise

    if "poi" in requested:
        try:
            result = await geocode_with_motis(
                snapshot,
                query,
                language=language,
                near=near,
                types=("poi",),
                limit=limit,
                request_id=request_id,
            )
            by_kind["poi"] = result.items
            searched.update(result.searched_types)
        except GeocoderUnavailable:
            unavailable.add("poi")

    if not searched:
        raise GeocoderUnavailable("All requested geocoding categories are unavailable")
    ordered_types = tuple(kind for kind in types if kind in searched)
    ordered_unavailable = tuple(kind for kind in types if kind in unavailable)
    items = [item for kind in ("address", "poi") for item in by_kind[kind]]
    return GeocodingResult(items, ordered_types, ordered_unavailable)
