// How a line looks (look chosen by the user, 11 November 2026; client design, "Visual
// direction"): lines take their operator's colour so the vehicle can be recognised on the
// street, and every badge carries a vehicle icon, so the vehicle type never depends on
// colour alone. Operator colours are data, not design tokens: an operator without an entry
// falls back to the mode tokens (mode-bus, mode-rail).
//
// Sources: see the table below and the client design, "Operator colours". Keep it current
// when an operator repaints.

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

// Sourced 11 November 2026 (session API-BOARDS; table with source links in
// docs/client-design.md, "Operator colours"). `verified` is true only where a reliable source states the vehicles'
// (or the line's) colour; the hex is the operator's own brand value. Other entries are
// approximate: a brand colour read from the operator's own site, or sampled from its own
// photographs, for liveries that are mostly white with that colour as the graphic. Badges
// keep the sourced colour (text ≥ 4.5:1); map lines are lightened on the dark map to 4.5:1
// and darkened on the light map to 3:1 only when the sourced colour falls short.
// Operators without a reliable source (Superbus, Dan BaDarom, Dan Be'er Sheva, Golan,
// Electra Afikim Tahbura, Derech Egged, Galim, NTT, …) have no entry and use the mode tokens.

const ENTRIES: Record<string, Entry> = {
  // Green, kept through the 2026 rebrand: web.archive.org copy of
  // egged.co.il/Days-Article-4492-80-years-of-color.aspx; cars.walla.co.il/item/3811652 and
  // /item/3855373. Hex: egged.co.il brand colour.
  egged: {
    ids: ["3"],
    names: ["אגד", "Egged"],
    badge: { bg: "#008761", ink: "#ffffff" },
    line: { dark: "#00a073", light: "#008761" },
    verified: true,
  },
  // Blue, repainted fleet-wide in 2023: TheMarker, 27 April 2023. Hex: dan.co.il `--dan-blue`.
  dan: {
    ids: ["5"],
    names: ["דן", "Dan"],
    badge: { bg: "#205cab", ink: "#ffffff" },
    line: { dark: "#4e8cde", light: "#205cab" },
    verified: true,
  },
  // Approximate: silver body, large orange logo (official fleet photo on metropoline.com).
  // Hex: metropoline.com `--orange`.
  metropoline: {
    ids: ["15"],
    names: ["מטרופולין", "Metropoline"],
    badge: { bg: "#f78f1e", ink: "#1a1206" },
    line: { dark: "#f78f1e", light: "#c76b07" },
    verified: false,
  },
  // Approximate: train livery not found; corporate blue from the official logo
  // (web-umbraco.rail.co.il/media/s32bha2f/logo.svg). Trains also get a dashed centre.
  "israel-railways": {
    ids: ["2"],
    names: ["רכבת ישראל", "Israel Railways"],
    badge: { bg: "#00458a", ink: "#ffffff" },
    line: { dark: "#158aff", light: "#00458a" },
    verified: false,
  },
  // Approximate: white with a navy graphic (official illustration kavim-t.com/media/2y2dwy0q/
  // kavim.jpg). Hex: kavim-t.com brand colour.
  kavim: {
    ids: ["18"],
    names: ["קווים", "Kavim"],
    badge: { bg: "#003780", ink: "#ffffff" },
    line: { dark: "#2e88ff", light: "#003780" },
    verified: false,
  },
  // Approximate: white with a lime roof band and logo (photo on electra-afikim.co.il).
  // Hex: electra-afikim.co.il brand colour.
  "electra-afikim": {
    ids: ["25"],
    names: ["אלקטרה אפיקים", "Electra Afikim"],
    badge: { bg: "#9aca3c", ink: "#1a1206" },
    line: { dark: "#9aca3c", light: "#6b8e27" },
    verified: false,
  },
  // Approximate: white with a teal roof and graphic, sampled from tnufa-t.com/images/
  // tnufa_headers-2.jpg.
  tnufa: {
    ids: ["34"],
    names: ["תנופה", "Tnufa"],
    badge: { bg: "#00808d", ink: "#ffffff" },
    line: { dark: "#009cac", light: "#00808d" },
    verified: false,
  },
  // Approximate: sky blue over white, one livery in both clusters, sampled from
  // extrapt.co.il/images/update_pict_bus.png.
  extra: {
    ids: ["37", "38"],
    names: ["אקסטרה", "אקסטרה ירושלים", "Extra"],
    badge: { bg: "#029acd", ink: "#1a1206" },
    line: { dark: "#029acd", light: "#028fbe" },
    verified: false,
  },
  // Approximate: white with orange (official banner on nateevexpress.com). Hex: its
  // `--brand-orange`.
  "nateev-express": {
    ids: ["14"],
    names: ["נתיב אקספרס", "Nateev Express"],
    badge: { bg: "#f18a00", ink: "#1a1206" },
    line: { dark: "#f18a00", light: "#c37000" },
    verified: false,
  },
};

/**
 * Light rail is drawn in the Red Line's colour whoever operates it. Line colour #f42434 from
 * the NTA site's stylesheet (archived 20 December 2022); Jerusalem's L1 is a close red
 * (#ef3d45, j-t.org.il route map). The badge is darker (#d32f2f) so white text keeps 4.5:1.
 */
const LIGHT_RAIL: OperatorColour = {
  badge: { bg: "#d32f2f", ink: "#ffffff" },
  line: { dark: "#f64b58", light: "#f42434" },
  verified: true,
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
