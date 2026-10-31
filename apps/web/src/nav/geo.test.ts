import { describe, expect, it } from "vitest";
import {
  bearingDegrees,
  destinationPoint,
  distanceToLineMeters,
  haversineMeters,
  lineLengthMeters,
  pointAlongLine,
  projectOntoLine,
} from "./geo";

const telAviv = { latitude: 32.0853, longitude: 34.7818 };
const haifa = { latitude: 32.794, longitude: 34.9896 };
const eilat = { latitude: 29.5577, longitude: 34.9519 };

describe("haversineMeters", () => {
  it("measures known Israeli distances", () => {
    expect(haversineMeters(telAviv, haifa) / 1000).toBeCloseTo(81.1, 0);
    expect(haversineMeters(telAviv, eilat) / 1000).toBeCloseTo(281.5, 0);
    expect(haversineMeters(telAviv, telAviv)).toBe(0);
  });

  it("is symmetric and metre-accurate at street scale", () => {
    const a = { latitude: 32.0775, longitude: 34.7748 };
    const b = destinationPoint(a, 63, 250);
    expect(haversineMeters(a, b)).toBeCloseTo(250, 6);
    expect(haversineMeters(b, a)).toBeCloseTo(haversineMeters(a, b), 9);
  });
});

describe("bearing and destination", () => {
  it("round-trips", () => {
    for (const bearing of [0, 45, 90, 180, 270, 359]) {
      const b = destinationPoint(telAviv, bearing, 1000);
      expect(haversineMeters(telAviv, b)).toBeCloseTo(1000, 6);
      expect(bearingDegrees(telAviv, b)).toBeCloseTo(bearing % 360, 4);
    }
  });
});

describe("projection onto a line", () => {
  // An L-shaped line: 500 m east, then 500 m north.
  const a = { latitude: 32.08, longitude: 34.78 };
  const b = destinationPoint(a, 90, 500);
  const c = destinationPoint(b, 0, 500);
  const line = [a, b, c].map((p) => [p.longitude, p.latitude]);

  it("measures the line", () => {
    expect(lineLengthMeters(line)).toBeCloseTo(1000, 0);
    expect(lineLengthMeters([])).toBe(0);
  });

  it("projects a point beside the first segment", () => {
    const p = destinationPoint(destinationPoint(a, 90, 200), 180, 30);
    const projection = projectOntoLine(p, line)!;
    expect(projection.alongMeters).toBeCloseTo(200, 0);
    expect(projection.distanceMeters).toBeCloseTo(30, 0);
    expect(projection.segment).toBe(0);
  });

  it("projects onto the second segment and clamps beyond the ends", () => {
    const p = destinationPoint(destinationPoint(b, 0, 300), 90, 20);
    expect(projectOntoLine(p, line)!.alongMeters).toBeCloseTo(800, 0);
    const before = destinationPoint(a, 270, 100);
    expect(projectOntoLine(before, line)!.alongMeters).toBe(0);
    expect(projectOntoLine(before, line)!.distanceMeters).toBeCloseTo(100, 0);
    const after = destinationPoint(c, 0, 50);
    expect(projectOntoLine(after, line)!.alongMeters).toBeCloseTo(1000, 0);
  });

  it("respects a lower bound (looping routes)", () => {
    // Out and back on the same street: a point near the start matches the return pass.
    const out = destinationPoint(a, 90, 400);
    const loop = [a, out, a].map((p) => [p.longitude, p.latitude]);
    const p = destinationPoint(a, 90, 100);
    expect(projectOntoLine(p, loop)!.alongMeters).toBeCloseTo(100, 0);
    expect(projectOntoLine(p, loop, { minAlongMeters: 450 })!.alongMeters).toBeCloseTo(700, 0);
    expect(projectOntoLine(p, loop, { minAlongMeters: 5000 })!.alongMeters).toBeCloseTo(800, 0);
  });

  it("handles degenerate lines", () => {
    expect(projectOntoLine(a, [])).toBeNull();
    expect(distanceToLineMeters(a, [])).toBe(Infinity);
    expect(projectOntoLine(b, [[a.longitude, a.latitude]])!.distanceMeters).toBeCloseTo(500, 0);
  });

  it("finds a point along the line", () => {
    const p = pointAlongLine(line, 750)!;
    expect(haversineMeters(p, destinationPoint(b, 0, 250))).toBeLessThan(0.5);
    expect(pointAlongLine(line, 5000)).toEqual(c);
    expect(pointAlongLine([], 10)).toBeNull();
  });
});
