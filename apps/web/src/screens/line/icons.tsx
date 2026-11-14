// Stroke icons of the stops-and-lines boards (canvas `.st`: 20 px, stroke 1.8, round),
// paths copied verbatim from the canvas. Decorative: the control's own name carries the meaning.

const PATHS = {
  star: "m10 2.500 2.300 4.800 5.200.700-3.800 3.600 1 5.200L10 14.300l-4.700 2.500 1-5.200L2.500 8l5.200-.700z",
  /** Toward the inline end in Hebrew (the boards' "כל התחנות ‹"). */
  forward: "m12 5-5 5 5 5",
  down: "m5 8 5 5 5-5",
  up: "m5 12 5-5 5 5",
} as const;

export type StrokeIconName = keyof typeof PATHS;

export function StrokeIcon({ name, filled = false, className }: { name: StrokeIconName; filled?: boolean; className?: string }) {
  return (
    <svg
      className={["sl-icon", name === "forward" ? "sl-icon--forward" : "", className ?? ""].filter(Boolean).join(" ")}
      viewBox="0 0 20 20"
      fill={filled ? "currentColor" : "none"}
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
