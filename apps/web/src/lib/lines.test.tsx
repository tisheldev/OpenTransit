import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LineBadge } from "../components/ds";
import { THEME_COLORS, THEMES } from "../styles/tokens";
import { badgeStyle, OPERATOR_COLOURS, operatorColour, vehicleOf } from "./lines";

function luminance(hex: string): number {
  const channel = (offset: number) => {
    const c = parseInt(hex.slice(1 + offset, 3 + offset), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
}
function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

describe("line look (11 November 2026)", () => {
  it("draws the vehicle from the API mode", () => {
    expect(["bus", "BUS", "", null, "coach"].map(vehicleOf)).toEqual(Array(5).fill("bus"));
    expect(["rail", "RAIL", "train"].map(vehicleOf)).toEqual(Array(3).fill("train"));
    expect(["light_rail", "tram", "subway", "metro"].map(vehicleOf)).toEqual(Array(4).fill("light-rail"));
  });

  it("finds the operator by MOT agency id or by the name the API returns, never by a partial name", () => {
    expect(operatorColour({ mode: "bus", operatorId: "3" })?.verified).toBe(true);
    expect(operatorColour({ mode: "bus", operatorName: "אגד" })).toBe(operatorColour({ mode: "bus", operatorId: "3" }));
    expect(operatorColour({ mode: "bus", operatorId: "5", operatorName: "דן" })?.badge.bg).toBe("#205cab");
    expect(operatorColour({ mode: "rail", operatorId: "2" })?.badge.bg).toBe("#00458a");
    // Other operators with similar names are not Dan or Egged.
    expect(operatorColour({ mode: "bus", operatorId: "32", operatorName: "דן באר שבע" })).toBeNull();
    expect(operatorColour({ mode: "bus", operatorId: "4", operatorName: "אגד תעבורה" })).toBeNull();
    expect(badgeStyle({ mode: "bus", operatorId: "16" })).toBeUndefined();
    // Light rail is drawn in the Red Line's colour whoever runs it.
    expect(operatorColour({ mode: "light_rail", operatorId: "3" })?.badge.bg).toBe("#d32f2f");
  });

  it("only colours a reliable source states are marked verified (Egged, Dan, the Red Line)", () => {
    expect(OPERATOR_COLOURS.filter((c) => c.verified)).toHaveLength(3);
  });

  it.each(OPERATOR_COLOURS.map((c) => [c.badge.bg, c] as const))("badge %s: its text ≥ 4.5:1", (_bg, colour) => {
    expect(contrast(colour.badge.ink, colour.badge.bg)).toBeGreaterThanOrEqual(4.5);
  });

  describe.each(THEMES)("%s map", (theme) => {
    it.each(OPERATOR_COLOURS.map((c) => [c.line[theme], c] as const))("line %s ≥ 3:1 on map-land and map-road", (_line, colour) => {
      expect(contrast(colour.line[theme], THEME_COLORS[theme]["map-land"])).toBeGreaterThanOrEqual(3);
      expect(contrast(colour.line[theme], THEME_COLORS[theme]["map-road"])).toBeGreaterThanOrEqual(2.8);
    });
  });

  it("a badge carries its vehicle icon and its operator's colour; an unknown operator keeps the mode colour", () => {
    const { container } = render(
      <>
        <LineBadge mode="bus" label="61" line={{ mode: "bus", operatorId: "5", operatorName: "דן" }} />
        <LineBadge mode="rail" label="רכבת" line={{ mode: "rail", operatorId: "2" }} />
        <LineBadge mode="rail" label="R1" line={{ mode: "light_rail", operatorId: "99" }} />
        <LineBadge mode="bus" label="18" line={{ mode: "bus", operatorId: "16" }} />
        <LineBadge mode="walk" label="5" />
      </>,
    );
    const [dan, train, lightRail, other, walk] = Array.from(container.querySelectorAll<HTMLElement>(".ot-line"));
    expect(dan!.dataset.vehicle).toBe("bus");
    expect(dan!.style.getPropertyValue("--line-bg")).toBe("#205cab");
    expect(dan!.querySelector("svg.ot-vehicle[aria-hidden='true']")).not.toBeNull();
    expect(dan!.querySelector("bdi.num")).toHaveTextContent("61");
    expect(train!.dataset.vehicle).toBe("train");
    // A Hebrew label is not set in the numeral face.
    expect(train!.querySelector("bdi")!.classList.contains("num")).toBe(false);
    expect(lightRail!.dataset.vehicle).toBe("light-rail");
    expect(lightRail!.style.getPropertyValue("--line-bg")).toBe("#d32f2f");
    expect(other!.style.getPropertyValue("--line-bg")).toBe("");
    expect(walk!.querySelector(".ot-i--walk")).not.toBeNull();
    expect(walk!.querySelector("svg")).toBeNull();
  });
});
