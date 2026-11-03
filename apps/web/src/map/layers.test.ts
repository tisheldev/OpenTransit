import { describe, expect, it } from "vitest";
import {
  OFFLINE_STYLE,
  OPENFREEMAP_STYLE,
  accuracyFeatures,
  chooseStyle,
  isNameTextField,
  nameExpression,
  pinFeatures,
  routeFeatures,
  sceneBounds,
  userFeatures,
} from "./layers";
import { emptyScene, type MapRouteLeg } from "./scene";

const walk: MapRouteLeg = { kind: "walk", mode: "walk", coordinates: null, from: [34.8, 32.1], to: [34.81, 32.11], label: null };
const bus: MapRouteLeg = {
  kind: "transit",
  mode: "bus",
  coordinates: [
    [34.81, 32.11],
    [34.9, 32.2],
  ],
  from: [34.81, 32.11],
  to: [34.9, 32.2],
  label: "8",
  active: true,
};

describe("scene to GeoJSON", () => {
  it("draws lines only for legs with geometry", () => {
    const { features } = routeFeatures([walk, bus]);
    expect(features).toHaveLength(1);
    expect(features[0]!.properties).toEqual({ kind: "transit", mode: "bus", active: true, label: "8" });
  });

  it("makes points for pins and the user, and a ring for accuracy", () => {
    expect(pinFeatures([{ id: "o", role: "origin", position: [34.8, 32.1], label: "A" }]).features[0]!.properties.role).toBe(
      "origin",
    );
    expect(userFeatures(null).features).toEqual([]);
    const user = { position: [34.8, 32.1] as [number, number], accuracyMeters: 50 };
    expect(userFeatures(user).features).toHaveLength(1);
    const ring = accuracyFeatures(user).features[0]!.geometry.coordinates[0]!;
    expect(ring[0]).toEqual(ring.at(-1));
    // 50 m north is ~0.00045 degrees of latitude.
    const maxLat = Math.max(...ring.map((p) => p[1]));
    expect(maxLat - 32.1).toBeCloseTo(0.00045, 4);
    expect(accuracyFeatures({ ...user, accuracyMeters: null }).features).toEqual([]);
  });

  it("frames route ends, geometry and pins, including a time-only walk's ends", () => {
    expect(sceneBounds(emptyScene)).toBeNull();
    expect(sceneBounds({ ...emptyScene, route: [walk, bus] })).toEqual([
      [34.8, 32.1],
      [34.9, 32.2],
    ]);
  });
});

describe("style choice and labels", () => {
  it("stays offline in fixtures and tests; OpenFreeMap otherwise; env override wins", () => {
    expect(chooseStyle("fixtures", undefined)).toBe(OFFLINE_STYLE);
    expect(chooseStyle("test", undefined)).toBe(OFFLINE_STYLE);
    expect(chooseStyle("production", undefined)).toBe(OPENFREEMAP_STYLE);
    expect(chooseStyle("production", "offline")).toBe(OFFLINE_STYLE);
    expect(chooseStyle("fixtures", "/my-style.json")).toBe("/my-style.json");
    expect(JSON.stringify(OFFLINE_STYLE)).not.toMatch(/https?:/);
  });

  it("prefers Hebrew names in Hebrew and Latin names in English", () => {
    expect(nameExpression("he")).toEqual(["coalesce", ["get", "name:he"], ["get", "name"]]);
    expect(JSON.stringify(nameExpression("en"))).toContain("name:en");
    expect(JSON.stringify(nameExpression("en"))).toContain("name:latin");
  });

  it("rewrites only name labels", () => {
    expect(isNameTextField("{name}")).toBe(true);
    expect(isNameTextField(["coalesce", ["get", "name_en"], ["get", "name"]])).toBe(true);
    expect(isNameTextField("{housenumber}")).toBe(false);
    expect(isNameTextField(["get", "ref"])).toBe(false);
    expect(isNameTextField(undefined)).toBe(false);
  });
});
