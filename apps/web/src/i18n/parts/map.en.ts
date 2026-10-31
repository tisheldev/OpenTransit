import type { he_map } from "./map.he";

// Mirrors map.he.ts key for key.
export const en_map: Record<keyof typeof he_map, string> = {
  "map.attribution.osm": "© OpenStreetMap contributors",
  "map.attribution.tiles": "Map tiles: OpenFreeMap",
  "map.attribution.mot": "Timetable: Ministry of Transport",
  "map.unavailable": "The map is unavailable right now",
  "map.pickPin": "The chosen location is at the map centre",
};
