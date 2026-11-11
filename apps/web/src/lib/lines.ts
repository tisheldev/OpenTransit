// How a line looks (look chosen by the user, 11 November 2026; client design, "Visual
// direction"): lines take their operator's colour so the vehicle can be recognised on the
// street, and every badge carries a vehicle icon, so the vehicle type never depends on
// colour alone. Operator colours are data, not design tokens: an operator without an entry
// falls back to the mode tokens (mode-bus, mode-rail).
//
// NOT VERIFIED: only Egged's green is checked against a source
// (https://egged.co.il/Days-Article-4492-80-years-of-color.aspx). The others are the
// example colours drawn on the approved boards. Build this table from the real vehicles and
// keep it current when an operator repaints (client design, "Open before the look is built").

import type { ThemeName } from "../styles/tokens";

export type Vehicle = "bus" | "train" | "light-rail";

/** The vehicle drawn on a badge, from the API leg mode ("bus", "rail", "light_rail", …). */
export function vehicleOf(mode: string | null | undefined): Vehicle {
  const value = (mode ?? "").toLowerCase();
  if (/light_rail|tram|subway|metro|monorail/.test(value)) return "light-rail";
  if (/rail|train|funicular/.test(value)) return "train";
  return "bus";
}

export interface OperatorColour {
  /** Badge fill and its text: the same in both themes, as on the boards (4.5:1+). */
  badge: { bg: string; ink: string };
  /** Map line per theme: lighter on the dark map, the badge colour on the light one. */
  line: Record<ThemeName, string>;
  /** True only for a colour checked against a source. */
  verified: boolean;
}

interface Entry extends OperatorColour {
  /** GTFS agency ids in the MOT feed, and the operator names the API returns. */
  ids: string[];
  names: string[];
}

const ENTRIES: Record<string, Entry> = {
  egged: {
    ids: ["3"],
    names: ["אגד", "Egged"],
    badge: { bg: "#0b8043", ink: "#ffffff" },
    line: { dark: "#3fbf7a", light: "#0b8043" },
    verified: true,
  },
  dan: {
    ids: ["5"],
    names: ["דן", "Dan"],
    badge: { bg: "#1565c0", ink: "#ffffff" },
    line: { dark: "#5b9bff", light: "#1565c0" },
    verified: false,
  },
  metropoline: {
    ids: ["15"],
    names: ["מטרופולין", "Metropoline"],
    badge: { bg: "#f08a00", ink: "#1a1206" },
    // Light map: darker than the boards' #f08a00, which is 2.2:1 on map-land (measured 11 Nov).
    line: { dark: "#ffa23a", light: "#c26e00" },
    verified: false,
  },
  "israel-railways": {
    ids: ["2"],
    names: ["רכבת ישראל", "Israel Railways"],
    badge: { bg: "#4a3fb0", ink: "#ffffff" },
    line: { dark: "#9a8fff", light: "#4a3fb0" },
    verified: false,
  },
};

/** Light rail is drawn in the Red Line's colour whoever operates it (example, as on the boards). */
const LIGHT_RAIL: OperatorColour = {
  badge: { bg: "#d32f2f", ink: "#ffffff" },
  line: { dark: "#ff6259", light: "#d32f2f" },
  verified: false,
};

export interface LineSource {
  mode: string | null | undefined;
  operatorId?: string | null;
  operatorName?: string | null;
}

/** The operator's colour for a line, or null when the table has none (use the mode tokens). */
export function operatorColour(source: LineSource): OperatorColour | null {
  if (vehicleOf(source.mode) === "light-rail") return LIGHT_RAIL;
  const id = source.operatorId?.trim() ?? "";
  const name = source.operatorName?.trim() ?? "";
  for (const entry of Object.values(ENTRIES)) {
    if ((id && entry.ids.includes(id)) || (name && entry.names.includes(name))) return entry;
  }
  return null;
}

/** Every entry, for the contrast test. */
export const OPERATOR_COLOURS: readonly OperatorColour[] = [...Object.values(ENTRIES), LIGHT_RAIL];

/** CSS custom properties for a badge in its operator's colour (none: the mode tokens apply). */
export function badgeStyle(source: LineSource): Record<string, string> | undefined {
  const colour = operatorColour(source);
  return colour ? { "--line-bg": colour.badge.bg, "--line-ink": colour.badge.ink } : undefined;
}
