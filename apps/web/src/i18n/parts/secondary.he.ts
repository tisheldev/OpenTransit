// Hebrew strings owned by the secondary slice; merged into he.ts. Keys are "<area>.<name>".
export const he_secondary = {
  // A stop (board 7, 11 November 2026): every line through it, tap one to see its route.
  "stop.lines": "הקווים בתחנה",
  "stop.minutes": "{minutes} דק׳",
  "stop.train": "רכבת",
  "stop.pin": "התחנה {stop}",
  "stop.line.end": "קו {line} נוסע אל {headsign}",
  "stop.line.endNoHeadsign": "קו {line}, סוף המסלול",
  "stop.direction": "כיוון הנסיעה של קו {line}",
  "stop.scheduled": "זמנים לפי לוח הזמנים",
  // The map's direction tags (user review, 14 November 2026): one per way out of the stop.
  "stop.towards": "לכיוון {place}",
  "stop.wayCount": "{count} קווים בכיוון הזה",
  "stop.allLines": "כל הקווים",
} as const;
