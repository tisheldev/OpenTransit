import type { he_secondary } from "./secondary.he";

// Mirrors secondary.he.ts key for key.
export const en_secondary: Record<keyof typeof he_secondary, string> = {
  "stop.lines": "Lines at this stop",
  "stop.minutes": "{minutes} min",
  "stop.train": "Train",
  "stop.pin": "Stop {stop}",
  "stop.line.end": "Line {line} goes to {headsign}",
  "stop.line.endNoHeadsign": "Line {line}, end of the route",
  "stop.direction": "Direction of travel of line {line}",
  "stop.scheduled": "Times from the timetable",
};
