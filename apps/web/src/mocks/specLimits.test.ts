import { describe, expect, it } from "vitest";
import { NEARBY_PER_STOP, NEARBY_STOPS } from "../screens/home/homeStops";
import { outsideSpec } from "./specLimits";

const at = (path: string) => new URL(`http://localhost:5173${path}`);

describe("query parameters against the API's own bounds (openapi.json)", () => {
  it("refuses what the API refuses: perStop over 5 on nearby departures (seen on real data, 14 November)", () => {
    expect(outsideSpec(at("/v1/departures/nearby?near=32.08,34.78&from=2026-11-14T23:00:00%2B02:00&perStop=6"))).toBe("perStop");
    expect(outsideSpec(at("/v1/departures/nearby?near=32.08,34.78&from=2026-11-14T23:00:00%2B02:00&perStop=5&stops=12"))).toBeNull();
    expect(outsideSpec(at("/v1/departures/nearby?near=32.08,34.78&stops=13"))).toBe("stops");
    expect(outsideSpec(at("/v1/departures/nearby?near=32.08,34.78&radius=0"))).toBe("radius");
  });

  it("matches paths with ids, and leaves paths the spec does not know alone", () => {
    expect(outsideSpec(at("/v1/stops/mot%3Astop%3A1/departures?limit=0"))).toBe("limit");
    expect(outsideSpec(at("/v1/stops/mot%3Astop%3A1/departures?limit=20"))).toBeNull();
    expect(outsideSpec(at("/v1/nowhere?limit=999999"))).toBeNull();
  });

  it("Home's nearby request is within the bounds", () => {
    expect(outsideSpec(at(`/v1/departures/nearby?near=32.08,34.78&from=2026-11-14T23:00:00%2B02:00&radius=400&stops=${NEARBY_STOPS}&perStop=${NEARBY_PER_STOP}&horizonMinutes=60`))).toBeNull();
  });
});
