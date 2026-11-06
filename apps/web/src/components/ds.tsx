import type { ReactNode } from "react";
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
 * A line as a solid badge with its mode icon (design: LineBadge): bus in mode-bus; rail,
 * light rail and metro in mode-rail; walking unfilled with its minutes. The label (a line
 * number, "רכבת", or minutes) is isolated in <bdi> with tabular figures.
 */
export function LineBadge({ mode, label, size, className }: { mode: LineMode; label: ReactNode; size?: "lg"; className?: string }) {
  const classes = ["ot-line", mode === "bus" ? "" : `ot-line--${mode}`, size ? `ot-line--${size}` : "", className ?? ""]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={classes}>
      <Icon name={mode === "rail" ? "train" : mode} />
      <bdi className="num">{label}</bdi>
    </span>
  );
}

/** Where a time comes from (design: StatusTag). Realtime is deferred: always "מתוכנן". */
export function StatusTag({ className }: { className?: string }) {
  const { t } = useI18n();
  return <span className={["ot-tag", className ?? ""].filter(Boolean).join(" ")}>{t("time.scheduled")}</span>;
}
