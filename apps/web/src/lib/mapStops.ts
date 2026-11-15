// Which stops Home's map draws below street zoom (user, 15 November 2026). On real data the
// neighbourhood view was crowded ("this way too bloated ... I want to see the map"); the user
// tried two options behind a Settings switch and chose "only the listed stops": the stops
// Home's sheet lists and the chosen stop are signs, and no other stop is drawn until street
// zoom. The other option, every other stop as a small muted dot that opens its stop, is kept
// behind a build flag so it can come back: VITE_MAP_STOP_DOTS=1.

export type HomeOtherStops = "dots" | "hidden";

/** How Home's map draws the stops its sheet does not list, below street zoom. */
export function homeOtherStops(flag: string | undefined = import.meta.env.VITE_MAP_STOP_DOTS): HomeOtherStops {
  return flag === "1" ? "dots" : "hidden";
}
