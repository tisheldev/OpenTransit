import type { he_map } from "./map.he";

// Mirrors map.he.ts key for key.
export const en_map: Record<keyof typeof he_map, string> = {
  "map.attribution.osm": "© OpenStreetMap",
  "map.attribution.tiles": "OpenFreeMap",
  // Short, so the credits stay one caption-size line beside Back at 360 px; Settings
  // names the Israel Ministry of Transport in full.
  "map.attribution.mot": "Israel MoT",
  "map.unavailable": "The map is unavailable right now",
  "map.pickPin": "The chosen location is at the map centre",
};
