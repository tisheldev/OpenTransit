import { createContext, useContext } from "react";

// The bottom sheet's snap points (design: Surface; tokens --sheet-peek/half/full).

export type Snap = "peek" | "half" | "full";
export const SNAPS: readonly Snap[] = ["peek", "half", "full"];
export const SNAP_FRACTION: Record<Snap, number> = { peek: 0.35, half: 0.55, full: 0.92 };

export interface SheetControl {
  snap: Snap;
  /**
   * Stable for a route (same identity until the route changes), so a screen may call it
   * from an effect without fighting the passenger's own drag or tap on the handle. Every
   * route opens at `defaultSnap`; a screen changes it only in response to something
   * (Search's "choose on map" drops to peek; Compare may open full for a tapped option).
   */
  setSnap: (snap: Snap) => void;
}

export const SheetContext = createContext<SheetControl>({ snap: "half", setSnap: () => {} });

/** Screens read or change the sheet's snap (Search drops it to peek to pick on the map). */
export function useSheet(): SheetControl {
  return useContext(SheetContext);
}

/**
 * The snap a screen opens at: text entry and long lists get the full sheet; screens with
 * something on the map (Home, Compare's route, Navigate's position) open at half.
 */
export function defaultSnap(routeName: string): Snap {
  return routeName === "search" || routeName === "settings" ? "full" : "half";
}

/**
 * The full sheet stops below whatever floats at the top (banners, Back, the map
 * attribution), so nothing there ever covers the sheet's content or is covered by it.
 */
export function fullHeight(viewportPx: number, topReservedPx: number): number {
  return Math.max(0, Math.min(SNAP_FRACTION.full * viewportPx, viewportPx - topReservedPx));
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
