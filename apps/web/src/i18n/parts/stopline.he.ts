// Hebrew strings of the stops-and-lines screens (canvas boards Stop 3, Line 4, Ride 5 and
// Journey 6, 14 November 2026; copy text from the boards); merged into he.ts.
export const he_stopline = {
  "screen.line": "קו",
  "screen.ride": "נסיעה בקו",

  // Stop (board 3)
  "stop.walkMinutes": "{minutes} דק׳ הליכה",
  "stop.save": "שמירת התחנה",
  "stop.travelFrom": "לנסוע מכאן",
  "stop.travelTo": "להגיע לכאן",
  "stop.allStops": "כל התחנות",
  "stop.nextTimes": "הזמנים הבאים של קו {line}",

  // Line (board 4)
  "line.title": "קו {line}",
  "line.every": "כל {minutes} דק׳ בערך",
  "line.mode.bus": "אוטובוס",
  "line.mode.rail": "רכבת",
  "line.mode.lightRail": "רכבת קלה",
  "line.save": "שמירת הקו",
  "line.towards": "ל{place}",
  "line.directions": "כיוון הנסיעה",
  "line.stops": "התחנות של הקו",
  "line.earlier": "{n} תחנות קודמות · מ{origin}",
  "line.earlier.one": "תחנה קודמת אחת · מ{origin}",
  "line.more": "{n} תחנות נוספות",
  "line.more.one": "תחנה נוספת אחת",
  "line.nearest": "הכי קרובה אליך · {minutes} דק׳ הליכה",
  "line.in": "בעוד {minutes} דק׳",
  "line.lightRail": "רכבת קלה",
  "line.note": "הקישו על תחנה כדי לרדת בה · זמנים לפי לוח הזמנים",
  "line.notFound": "הקו לא נמצא בלוח הזמנים.",

  // Ride it (board 5)
  "ride.when": "מתי עולים ב{stop}?",
  "ride.departures": "נסיעות",
  "ride.board": "עולים כאן",
  "ride.boardWalk": "עולים כאן · {minutes} דק׳ הליכה",
  "ride.alight": "יורדים כאן · {stops} · {minutes} דק׳ נסיעה",
  "ride.getOff": "יורדים כאן",
  "ride.summaryWalk": "{duration} · כולל {walk} הליכה לתחנה",
  "ride.continue": "ולהמשיך משם…",
  "ride.pick": "הקישו על התחנה שבה יורדים",
  "ride.missed": "ההליכה לתחנה ארוכה מהזמן עד היציאה הזו",
  "ride.expired": "הנסיעה הזו כבר לא זמינה. בחרו קו ותחנה שוב.",

  // A line opened inside a journey (board 6)
  "route.lineHere": "קו {line} מהתחנה הזו · אפשר לבחור נסיעה אחרת",
  "route.allStopsOf": "כל התחנות של קו {line}",
} as const;
