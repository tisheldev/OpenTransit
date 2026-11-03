# Nav test data

`recorded-oct31a-dizengoff-technion.json` — recorded on 31 October 2026 from the local OpenTransit API
(`http://127.0.0.1:8590`, generation in `source.generationId`, rate limiter off), read-only:

- `journeys`: `POST /v1/journeys` Dizengoff Center `mot:stop:13583` → Technion `32.7767,35.0231`,
  depart `2026-11-02T08:00:00+02:00`, 3 results (warning `TRANSFER_STREET_PATH_UNAVAILABLE`; journey 1 has a
  time-only transfer walk with `geometry: null`, `distanceMeters: null`).
- `trips`: `GET /v1/trips/{engineTripId}` for every transit leg; `shape` set to null (the engine uses leg geometry).
- `stopPositions`: latitude/longitude from `GET /v1/stops/{id}` for each call between a ride's boarding and exit
  (stand-in for API-C1 call coordinates).

Sanitised: `requestId`s removed. Positions produced from it by `simulate.ts` are simulated, not recorded.
