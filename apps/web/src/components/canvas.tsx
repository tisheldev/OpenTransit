import type { CSSProperties } from "react";
import { badgeStyle, vehicleOf, type LineSource } from "../lib/lines";
import "./canvas.css";

// Pieces drawn exactly as on the stops-and-lines canvas (user, 14 November 2026: "make sure
// the client looks exactly like the claude design artifact including animations, logos and
// colors"): the line badge (24 px, corner 6, Barlow Semi Condensed 700 15 px, a 13 px
// vehicle), the mustard stop sign, and the 20 px stroke icons. Icon paths are copied
// verbatim from the canvas boards (Main, Search, Stop, Line). Badge colours stay the
// operator's (src/lib/lines.ts).

/** Solid vehicle shapes on a 16 px grid, from the canvas's `.bdg` and `.sg` icons. */
export const CANVAS_VEHICLE_PATHS = {
  bus: "M3 3a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v9h-1v2h-2v-2H6v2H4v-2H3zm2 0v4h6V3zm0 6v1.5h1.5V9zm4.5 0v1.5H11V9z",
  rail: "M4 1h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2l1.5 2h-2L10 13H6l-1.5 2h-2L4 13a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2zm0 2.5V7h8V3.5zM5 9v1.5h1.5V9zm4.5 0v1.5H11V9z",
} as const;

export type CanvasVehicle = keyof typeof CANVAS_VEHICLE_PATHS;

/** Stroke icons on a 20 px grid (canvas `.st`): drawn in currentColor, 1.8 wide. */
const STROKE_ICONS = {
  search: (
    <>
      <circle cx="9" cy="9" r="6" />
      <path d="m14 14 4 4" />
    </>
  ),
  // Points the way back: right in Hebrew; mirrored in English (canvas-icon--mirror).
  back: <path d="M4 10h12M11 5l5 5-5 5" />,
  close: <path d="m5 5 10 10M15 5 5 15" />,
  // Points onward: left in Hebrew; mirrored in English.
  chevron: <path d="m12 5-5 5 5 5" />,
  chevronDown: <path d="m5 8 5 5 5-5" />,
  clock: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 6v4l3 2" />
    </>
  ),
  pin: (
    <>
      <path d="M10 18s6-5.5 6-10a6 6 0 0 0-12 0c0 4.500 6 10 6 10z" />
      <circle cx="10" cy="8" r="2" />
    </>
  ),
  star: <path d="m10 2.500 2.300 4.800 5.200.700-3.800 3.600 1 5.200L10 14.300l-4.700 2.500 1-5.200L2.500 8l5.200-.700z" />,
} as const;

export type CanvasIconName = keyof typeof STROKE_ICONS;

/** Icons that point along the reading direction: mirrored in a left-to-right page. */
const DIRECTIONAL: ReadonlySet<CanvasIconName> = new Set(["back", "chevron"]);

/** A 20 px stroke icon from the canvas; decorative (its button or text carries the meaning). */
export function CanvasIcon({ name, className, style }: { name: CanvasIconName; className?: string; style?: CSSProperties }) {
  const classes = ["cv-st", DIRECTIONAL.has(name) ? "cv-st--dir" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <svg className={classes} style={style} viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      {STROKE_ICONS[name]}
    </svg>
  );
}

/** A solid vehicle on the canvas's 16 px grid, in currentColor; decorative. */
export function CanvasVehicleIcon({ vehicle, className }: { vehicle: CanvasVehicle; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path fillRule="evenodd" d={CANVAS_VEHICLE_PATHS[vehicle]} />
    </svg>
  );
}

/** The canvas draws every rail-like mode (train, light rail, metro) with its train icon. */
export const canvasVehicle = (mode: string | null | undefined): CanvasVehicle => (vehicleOf(mode) === "bus" ? "bus" : "rail");

export interface BadgeSource extends LineSource {
  /** The line number, or the train word for a train without one. */
  label: string;
}

/**
 * A line's badge as on the canvas (`.bdg`): the vehicle and the number, in the operator's
 * colour when the operator table has one, else the mode tokens. The number is isolated in
 * <bdi> so "8" and "172" never reorder inside Hebrew text.
 */
export function CanvasBadge({ line, className }: { line: BadgeSource; className?: string }) {
  const vehicle = canvasVehicle(line.mode);
  const classes = ["cv-bdg", vehicle === "rail" ? "cv-bdg--rail" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <span className={classes} style={badgeStyle(line) as CSSProperties | undefined} data-vehicle={vehicle}>
      <CanvasVehicleIcon vehicle={vehicle} />
      <bdi>{line.label}</bdi>
    </span>
  );
}

/**
 * The stop sign as a list lead or chip (marker G off the map): mustard with the bus icon;
 * a train or light-rail station is the purple sign with the train. `chip` is the 18 px
 * sign beside a saved stop's name (Home); `lead` the 32 px sign that starts a stop row.
 */
export function StopSign({ size, station = false }: { size: "chip" | "lead"; station?: boolean }) {
  return (
    <span className={`cv-sign cv-sign--${size}${station ? " cv-sign--station" : ""}`} aria-hidden="true">
      <CanvasVehicleIcon vehicle={station ? "rail" : "bus"} />
    </span>
  );
}

/** A place row's quiet lead (canvas `.lead`): a pin in a 32 px round. */
export function PlaceLead() {
  return (
    <span className="cv-lead" aria-hidden="true">
      <CanvasIcon name="pin" className="cv-st--16" />
    </span>
  );
}
