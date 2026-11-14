import type { CSSProperties, ReactNode } from "react";
import { badgeStyle } from "../../lib/lines";
import type { MapTagLine } from "../scene";
import { lineMode } from "../layers";
import type { PoleSide } from "./geometry";

// Marker G as drawn on the canvas (stops and lines, 12 November 2026): the mustard sign
// with its bus, its pole and kerb dot; the chosen sign; the purple station sign with its
// train; the neighbourhood square; a group's count; the next-line flag tag. Every shape is
// placed around its stop's kerb point (0, 0); stops.css holds the sizes and colours.

/** The canvas bus icon (16 × 16), verbatim. */
export const BUS_PATH =
  "M3 3a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v9h-1v2h-2v-2H6v2H4v-2H3zm2 0v4h6V3zm0 6v1.5h1.5V9zm4.5 0v1.5H11V9z";
/** The canvas train icon (16 × 16), verbatim. */
export const TRAIN_PATH =
  "M4 1h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2l1.5 2h-2L10 13H6l-1.5 2h-2L4 13a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2zm0 2.5V7h8V3.5zM5 9v1.5h1.5V9zm4.5 0v1.5H11V9z";
/** The canvas zoom-in magnifier (20 × 20, stroked), for the far-out hint. */
export const ZOOM_IN_PATH = "m14 14 4 4M9 6.500v5M6.500 9h5";

export function CanvasIcon({ path, className }: { path: string; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path fillRule="evenodd" d={path} />
    </svg>
  );
}

export type SignSide = PoleSide | "centre";

/** The pole and kerb dot for a side (none when centred). */
export function Pole({ side }: { side: SignSide }) {
  if (side === "centre") return null;
  return (
    <>
      <span className={`ot-stop-pole ot-stop-pole--${side}`} aria-hidden="true" />
      <span className="ot-stop-dot" aria-hidden="true" />
    </>
  );
}

/** The sign face: mustard with the bus, bright when chosen, purple with the train for a station. */
export function SignFace({ kind, chosen }: { kind: "stop" | "station"; chosen?: boolean }) {
  const className = ["ot-stop-sign", kind === "station" ? "ot-stop-sign--station" : "", chosen ? "ot-stop-sign--chosen" : ""].filter(Boolean).join(" ");
  return (
    <span className={className} aria-hidden="true">
      <CanvasIcon path={kind === "station" ? TRAIN_PATH : BUS_PATH} />
    </span>
  );
}

/**
 * A tap target of at least 44 px around a marker (design: "The tap area is at least 44 px
 * whatever the drawn size"); a plain image when it does nothing (the quiet layer).
 */
export function Hit({
  className,
  style,
  label,
  onSelect,
  children,
}: {
  className: string;
  style?: CSSProperties;
  label: string;
  onSelect?: () => void;
  children: ReactNode;
}) {
  if (!onSelect) {
    return (
      <span className={`ot-stop-hit ${className}`} style={style} aria-hidden="true">
        {children}
      </span>
    );
  }
  return (
    <button type="button" className={`ot-stop-hit ${className}`} style={style} aria-label={label} onClick={onSelect}>
      {children}
    </button>
  );
}

/** A line's badge on a tag: the operator's colour and the canvas bus or train. */
export function TagBadge({ line }: { line: MapTagLine }) {
  const rail = lineMode(line.mode) === "rail";
  return (
    <span className={`ot-tag-badge${rail ? " ot-tag-badge--rail" : ""}`} style={badgeStyle(line) as CSSProperties | undefined}>
      <CanvasIcon path={rail ? TRAIN_PATH : BUS_PATH} />
      <bdi className={/\d/.test(line.label) ? "num" : undefined}>{line.label}</bdi>
    </span>
  );
}
