import type { he_stops } from "./stops.he";

// Mirrors stops.he.ts key for key.
export const en_stops: Record<keyof typeof he_stops, string> = {
  "stops.sign": "Open stop {stop}",
  "stops.sign.next": "Open stop {stop}, line {line} in {minutes} min",
  "stops.unnamed": "Stop",
  "stops.group": "{count} stops close together, tap to open them",
  "stops.hint": "Zoom in to see bus stops",
  "stops.area": "In this area",
  "stops.area.distance": "{distance} from you",
  "stops.toMe": "To me",
  "stops.toMe.label": "Back to my location",
  "stops.group.title": "{name} · {count} stops",
  "stops.group.ask": "Which way are you going?",
  "stops.group.list": "The stops in this group",
  "stops.group.openHint": "Tap again to open the stop",
  "stops.dir.north": "Northbound",
  "stops.dir.east": "Eastbound",
  "stops.dir.south": "Southbound",
  "stops.dir.west": "Westbound",
};
