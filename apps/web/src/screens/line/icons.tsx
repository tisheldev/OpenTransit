import { CanvasIcon, type CanvasIconName } from "../../components/canvas";

// The stops-and-lines screens' stroke icons: the canvas's own (components/canvas.tsx, paths
// copied verbatim), plus the folding chevron pointing up (board Journey: "m5 12 5-5 5 5").

export type StrokeIconName = "star" | "forward" | "down" | "up";

const CANVAS: Record<Exclude<StrokeIconName, "up">, CanvasIconName> = { star: "star", forward: "chevron", down: "chevronDown" };

export function StrokeIcon({ name, filled = false, className }: { name: StrokeIconName; filled?: boolean; className?: string }) {
  if (name === "up") {
    return (
      <svg className={["cv-st", className ?? ""].filter(Boolean).join(" ")} viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <path d="m5 12 5-5 5 5" />
      </svg>
    );
  }
  return <CanvasIcon name={CANVAS[name]} className={className} style={filled ? { fill: "currentColor" } : undefined} />;
}
