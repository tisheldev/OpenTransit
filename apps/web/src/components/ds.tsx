import type { CSSProperties, ReactNode } from "react";
import { badgeStyle, vehicleOf, type LineSource, type Vehicle } from "../lib/lines";
import { useI18n } from "../i18n/I18nProvider";

// Small React wrappers over the design system's component classes (ot-*, in
// styles/design-system/bundle.css). Screens use the classes directly for layout; these
// three recur everywhere and carry their own accessibility rules.

export type IconName =
  | "search"
  | "home"
  | "work"
  | "star"
  | "pin"
  | "locate"
  | "clock"
  | "swap"
  | "chevron"
  | "back"
  | "close"
  | "bus"
  | "train"
  | "walk"
  | "stop"
  | "route"
  | "map"
  | "info"
  | "alert"
  | "plus";

/** A line icon in currentColor; decorative (the text next to it carries the meaning). */
export function Icon({ name, size, className }: { name: IconName; size?: "sm" | "lg"; className?: string }) {
  const classes = ["ot-i", `ot-i--${name}`, size ? `ot-i--${size}` : "", className ?? ""].filter(Boolean).join(" ");
  return <span className={classes} aria-hidden="true" />;
}

export type LineMode = "bus" | "rail" | "walk";

/**
 * Solid vehicle shapes (look of 11 November 2026: a simple vehicle icon on every line). Bus
 * and train are the stops-and-lines canvas's own 16 px paths, copied verbatim (user, 14
 * November 2026: "exactly like the claude design"); light rail keeps its 24 px drawing.
 */
export const VEHICLE_ICONS: Record<Vehicle, { viewBox: string; d: string }> = {
  bus: { viewBox: "0 0 16 16", d: "M3 3a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v9h-1v2h-2v-2H6v2H4v-2H3zm2 0v4h6V3zm0 6v1.5h1.5V9zm4.5 0v1.5H11V9z" },
  train: {
    viewBox: "0 0 16 16",
    d: "M4 1h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2l1.5 2h-2L10 13H6l-1.5 2h-2L4 13a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2zm0 2.5V7h8V3.5zM5 9v1.5h1.5V9zm4.5 0v1.5H11V9z",
  },
  "light-rail": {
    viewBox: "0 0 24 24",
    d: "M9 1.5h6v1.4h-2.2v1.6H16a3 3 0 0 1 3 3V16a3 3 0 0 1-3 3l1.3 2.5h-2.1l-1-2H9.8l-1 2H6.7L8 19a3 3 0 0 1-3-3V7.5a3 3 0 0 1 3-3h3.2V2.9H9V1.5zM7.5 8v4.5h9V8h-9zM12 16.9a1.3 1.3 0 1 0 0-2.6 1.3 1.3 0 0 0 0 2.6z",
  },
};

/** A solid vehicle icon in currentColor; decorative (the badge text carries the meaning). */
export function VehicleIcon({ vehicle, className }: { vehicle: Vehicle; className?: string }) {
  const icon = VEHICLE_ICONS[vehicle];
  return (
    <svg className={["ot-vehicle", className ?? ""].filter(Boolean).join(" ")} viewBox={icon.viewBox} fill="currentColor" aria-hidden="true" focusable="false" data-vehicle={vehicle}>
      <path fillRule="evenodd" d={icon.d} />
    </svg>
  );
}

/**
 * A line as a solid badge (design: LineBadge; look of 11 November 2026): in its operator's
 * colour when the operator table has one (src/lib/lines.ts), else bus in mode-bus and rail,
 * light rail and metro in mode-rail; a solid vehicle icon beside the label; walking
 * unfilled with its minutes. The label (a line number, "רכבת", or minutes) is isolated in
 * <bdi>; digits use the signage numerals.
 */
export function LineBadge({
  mode,
  label,
  size,
  className,
  line,
}: {
  mode: LineMode;
  label: ReactNode;
  size?: "lg";
  className?: string;
  /** The leg's API mode and operator: picks the vehicle icon and the operator's colour. */
  line?: LineSource;
}) {
  const classes = ["ot-line", mode === "bus" ? "" : `ot-line--${mode}`, size ? `ot-line--${size}` : "", className ?? ""]
    .filter(Boolean)
    .join(" ");
  if (mode === "walk") {
    return (
      <span className={classes}>
        <Icon name="walk" />
        <bdi className="num">{label}</bdi>
      </span>
    );
  }
  const vehicle = line ? vehicleOf(line.mode) : mode === "rail" ? "train" : "bus";
  // Digits take the signage numerals; a Hebrew-only label ("רכבת") stays in Arimo, smaller.
  const numeric = typeof label === "string" || typeof label === "number" ? /\d/.test(String(label)) : true;
  return (
    <span className={classes} style={line ? (badgeStyle(line) as CSSProperties | undefined) : undefined} data-vehicle={vehicle}>
      <VehicleIcon vehicle={vehicle} />
      <bdi className={numeric ? "num" : undefined}>{label}</bdi>
    </span>
  );
}

/** Where a time comes from (design: StatusTag). Realtime is deferred: always "מתוכנן". */
export function StatusTag({ className }: { className?: string }) {
  const { t } = useI18n();
  return <span className={["ot-tag", className ?? ""].filter(Boolean).join(" ")}>{t("time.scheduled")}</span>;
}
