import { describe, expect, it } from "vitest";
import { StopsPageSchema } from "../api/schemas";
import { derivedAreaStops } from "./areaStops";

// The derived answer for the stops layer (A1): valid stop items, the mode filter, the area
// limits and paging.

const ask = (query: string) => derivedAreaStops(new URL(`http://localhost/v1/stops?${query}`));
const TEL_AVIV = "bbox=34.76,32.06,34.80,32.09";

describe("derived stops by area", () => {
  it("answers stop items with mode and direction, 100 to a page with a cursor", () => {
    const first = ask(`${TEL_AVIV}&limit=100`);
    expect(first.status).toBe(200);
    const body = StopsPageSchema.parse(first.body);
    expect(body.data.length).toBeGreaterThan(20);
    expect(body.data.every((stop) => stop.mode === "bus" || stop.mode === "rail")).toBe(true);
    expect(body.data.some((stop) => typeof stop.bearingDegrees === "number")).toBe(true);
    const small = StopsPageSchema.parse(ask(`${TEL_AVIV}&limit=10`).body);
    expect(small.data).toHaveLength(10);
    expect(small.page.nextCursor).toBe("derived-10");
    const next = StopsPageSchema.parse(ask(`${TEL_AVIV}&limit=10&cursor=derived-10`).body);
    expect(next.data[0]!.stopId).not.toBe(small.data[0]!.stopId);
  });

  it("filters by mode: rail and light rail alone give the stations", () => {
    const body = StopsPageSchema.parse(ask(`${TEL_AVIV}&mode=rail,light_rail&limit=100`).body);
    expect(body.data.length).toBeGreaterThan(0);
    expect(body.data.every((stop) => stop.mode === "rail" || stop.mode === "light_rail")).toBe(true);
  });

  it("keeps the 100 km² limit unless only stations are asked for (then 120,000 km²)", () => {
    const country = "bbox=34.2,29.5,35.9,33.3";
    expect(ask(country).status).toBe(422);
    expect(ask(`${country}&mode=bus`).status).toBe(422);
    expect(ask(`${country}&mode=rail,light_rail`).status).toBe(200);
  });
});
