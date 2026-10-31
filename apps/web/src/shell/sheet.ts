import { createContext, useContext } from "react";

// The bottom sheet's snap points (design: Surface; tokens --sheet-peek/half/full).

export type Snap = "peek" | "half" | "full";
export const SNAPS: readonly Snap[] = ["peek", "half", "full"];
export const SNAP_FRACTION: Record<Snap, number> = { peek: 0.35, half: 0.55, full: 0.92 };

export interface SheetControl {
  snap: Snap;
  setSnap: (snap: Snap) => void;
}

export const SheetContext = createContext<SheetControl>({ snap: "half", setSnap: () => {} });

/** Screens read or change the sheet's snap (Search drops it to peek to pick on the map). */
export function useSheet(): SheetControl {
  return useContext(SheetContext);
}

/** The snap a screen opens at: text entry and long lists get the full sheet. */
export function defaultSnap(routeName: string): Snap {
  return routeName === "search" || routeName === "settings" ? "full" : "half";
}

export function nearestSnap(heightPx: number, viewportPx: number): Snap {
  let best: Snap = "half";
  let distance = Infinity;
  for (const snap of SNAPS) {
    const gap = Math.abs(SNAP_FRACTION[snap] * viewportPx - heightPx);
    if (gap < distance) {
      best = snap;
      distance = gap;
    }
  }
  return best;
}

export function stepSnap(snap: Snap, direction: 1 | -1): Snap {
  const index = SNAPS.indexOf(snap) + direction;
  return SNAPS[Math.max(0, Math.min(SNAPS.length - 1, index))]!;
}
