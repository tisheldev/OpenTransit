import type { CSSProperties, ReactNode } from "react";
import { CANVAS_VEHICLE_PATHS } from "../../components/canvas";
import { badgeStyle } from "../../lib/lines";
import type { MapTagLine } from "../scene";
import { lineMode } from "../layers";
import type { PoleSide } from "./geometry";

// Marker G as drawn on the canvas (stops and lines, 12 November 2026): the mustard sign
// with its bus, its pole and kerb dot; the chosen sign; the purple station sign with its
// train; the neighbourhood square; a group's count; the next-line flag tag. Every shape is
// placed around its stop's kerb point (0, 0); stops.css holds the sizes and colours.

/** The canvas bus icon (16 × 16), verbatim (shared with the sheet: src/components/canvas.tsx). */
export const BUS_PATH = CANVAS_VEHICLE_PATHS.bus;
/** The canvas train icon (16 × 16), verbatim. */
export const TRAIN_PATH = CANVAS_VEHICLE_PATHS.rail;
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

/**
 * One marker G at its kerb point (0, 0 of its positioned parent), for a single stop drawn
 * outside the stops layer (the Stop, Line and Ride maps: MapOverlay's sign pins). The same
 * parts, sizes, tokens and pole rule as the layer's signs; a station is the centred purple sign.
 */
export function GMarker({
  side,
  chosen = false,
  station = false,
  label,
  onSelect,
}: {
  side: PoleSide | null;
  chosen?: boolean;
  station?: boolean;
  label: string;
  onSelect?: () => void;
}) {
  const shown: SignSide = station ? "centre" : (side ?? "centre");
  const className = ["ot-stop", `ot-stop--${shown}`, chosen && !station ? "ot-stop--chosen" : "", station ? "ot-stop--station" : ""].filter(Boolean).join(" ");
  return (
    <div className={className}>
      <div className="ot-stop__body">
        {!station && <Pole side={shown} />}
        {onSelect ? (
          <Hit className="ot-stop-hit--sign" label={label} onSelect={onSelect}>
            <SignFace kind={station ? "station" : "stop"} chosen={chosen && !station} />
          </Hit>
        ) : (
          <span className="ot-stop-hit ot-stop-hit--sign" role="img" aria-label={label}>
            <SignFace kind={station ? "station" : "stop"} chosen={chosen && !station} />
          </span>
        )}
      </div>
    </div>
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
