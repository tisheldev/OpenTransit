# Leaflet 1.9.4

Vendored distribution from <https://unpkg.com/leaflet@1.9.4/dist/> on September 30, 2026.
License from <https://github.com/Leaflet/Leaflet/blob/v1.9.4/LICENSE> is preserved in `LICENSE`.
No remote scripts are loaded by this client. Leaflet's optional developer source map is not bundled.

Verified SHA-256 integrity against the [official download page](https://leafletjs.com/download.html):

- `leaflet.js`: `20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=`
- `leaflet.css`: `p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=`

Street tiles are requested by the browser from `https://tile.openstreetmap.org/{z}/{x}/{y}.png`;
the map displays attribution and preserves browser caching and an origin referrer.
No prefetching, offline tile downloads or external geocoding is implemented.
See the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/)
before changing this local test harness into a publicly used client.
