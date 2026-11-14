// Where a tag pinned to a path sits (Stop, user review 14 November 2026): at the point
// where the path leaves the visible part of the map, so the tag reads "this way, and on
// beyond the map", or at the path's end when it never leaves. Pure screen geometry, so it
// unit-tests without MapLibre.

export interface ScreenPoint {
  x: number;
  y: number;
}

/** The visible part of the map in screen pixels (below the top band, above the sheet). */
export interface ScreenRect {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export type EdgeSide = "top" | "bottom" | "left" | "right";

export interface EdgePin extends ScreenPoint {
  /** The side the path leaves by; null when it ends in view. */
  side: EdgeSide | null;
}

const inside = (p: ScreenPoint, r: ScreenRect) => p.x >= r.left && p.x <= r.right && p.y >= r.top && p.y <= r.bottom;

/**
 * Where a path (its first point the stop) leaves the rectangle, else its last point; null
 * when the path's start is out of view (the stop panned away: the tag would point from
 * nowhere) or the path has fewer than two points.
 */
export function edgePin(path: readonly ScreenPoint[], rect: ScreenRect): EdgePin | null {
  if (path.length < 2 || !inside(path[0]!, rect)) return null;
  for (let index = 1; index < path.length; index += 1) {
    const a = path[index - 1]!;
    const b = path[index]!;
    if (inside(b, rect)) continue;
    // The share of a→b where it first meets a side.
    let best = 1;
    let side: EdgeSide = "top";
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const meet = (t: number, s: EdgeSide) => {
      if (t >= 0 && t < best) {
        best = t;
        side = s;
      }
    };
    if (dy < 0) meet((rect.top - a.y) / dy, "top");
    if (dy > 0) meet((rect.bottom - a.y) / dy, "bottom");
    if (dx < 0) meet((rect.left - a.x) / dx, "left");
    if (dx > 0) meet((rect.right - a.x) / dx, "right");
    return { x: a.x + dx * best, y: a.y + dy * best, side };
  }
  const last = path[path.length - 1]!;
  return { x: last.x, y: last.y, side: null };
}

/** Tags this close along the same side would overlap; the later one moves inward by a tag's height. */
const CLASH_ALONG_PX = 150;
const CLASH_ACROSS_PX = 34;
const STEP_PX = 36;

/** Moves pins on the same side apart so their tags do not cover each other (first come keeps its place). */
export function spreadPins(pins: ReadonlyArray<EdgePin | null>): Array<EdgePin | null> {
  const placed: EdgePin[] = [];
  return pins.map((pin) => {
    if (!pin) return null;
    const moved = { ...pin };
    const vertical = moved.side === "left" || moved.side === "right";
    for (let tries = 0; tries < 6; tries += 1) {
      const clash = placed.some((other) =>
        vertical
          ? Math.abs(other.y - moved.y) < CLASH_ACROSS_PX && Math.abs(other.x - moved.x) < CLASH_ALONG_PX
          : Math.abs(other.x - moved.x) < CLASH_ALONG_PX && Math.abs(other.y - moved.y) < CLASH_ACROSS_PX,
      );
      if (!clash) break;
      if (moved.side === "top") moved.y += STEP_PX;
      else if (moved.side === "bottom") moved.y -= STEP_PX;
      else if (moved.side === "left" || moved.side === "right") moved.y += STEP_PX;
      else moved.y -= STEP_PX;
    }
    placed.push(moved);
    return moved;
  });
}
