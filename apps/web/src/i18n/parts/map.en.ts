import type { he_map } from "./map.he";

// Mirrors map.he.ts key for key.
export const en_map: Record<keyof typeof he_map, string> = {
  "map.attribution.osm": "© OpenStreetMap",
  "map.attribution.tiles": "OpenFreeMap",
  "map.attribution.mot": "Ministry of Transport",
  "map.unavailable": "The map is unavailable right now",
  "map.pickPin": "The chosen location is at the map centre",
};
