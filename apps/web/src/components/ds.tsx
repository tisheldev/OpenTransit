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

/** Solid vehicle shapes on a 24 px grid (look of 11 November 2026: a simple vehicle icon on every line). */
const VEHICLE_PATHS: Record<Vehicle, string> = {
  bus: "M6 3h12a3 3 0 0 1 3 3v10a2 2 0 0 1-2 2v1.5a1.5 1.5 0 0 1-3 0V18H8v1.5a1.5 1.5 0 0 1-3 0V18a2 2 0 0 1-2-2V6a3 3 0 0 1 3-3zm0 3.5v5h12v-5H6zm1.6 9.2a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4zm8.8 0a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4z",
  train:
    "M8 2.5h8a4 4 0 0 1 4 4V15a3 3 0 0 1-3 3l1.6 3h-2.2l-1.1-2H8.7l-1.1 2H5.4L7 18a3 3 0 0 1-3-3V6.5a4 4 0 0 1 4-4zm-1 4.5v4h10V7H7zm1.5 8.2a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4zm7 0a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4z",
  "light-rail":
    "M9 1.5h6v1.4h-2.2v1.6H16a3 3 0 0 1 3 3V16a3 3 0 0 1-3 3l1.3 2.5h-2.1l-1-2H9.8l-1 2H6.7L8 19a3 3 0 0 1-3-3V7.5a3 3 0 0 1 3-3h3.2V2.9H9V1.5zM7.5 8v4.5h9V8h-9zM12 16.9a1.3 1.3 0 1 0 0-2.6 1.3 1.3 0 0 0 0 2.6z",
};

/** A solid vehicle icon in currentColor; decorative (the badge text carries the meaning). */
export function VehicleIcon({ vehicle, className }: { vehicle: Vehicle; className?: string }) {
  return (
    <svg className={["ot-vehicle", className ?? ""].filter(Boolean).join(" ")} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false" data-vehicle={vehicle}>
      <path fillRule="evenodd" d={VEHICLE_PATHS[vehicle]} />
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
