// Hebrew strings for Home and Search in the stops-and-lines overhaul (canvas boards 1 and 2,
// 14 November 2026); merged into he.ts. Keys are "<area>.<name>".
export const he_homeSearch = {
  "screen.line": "קו",

  // Home (board 1): the field's hint, saved stops and lines, lines near the passenger.
  "home.search.hint": "מקום, תחנה או קו",
  "home.near.title": "קרוב אליך",
  "home.near.walk": "עד {minutes} דק׳ הליכה",
  "home.near.from": "{stop} · {minutes} דק׳ הליכה",
  "home.near.none": "אין קווים שיוצאים בשעה הקרובה מהתחנות הקרובות.",
  "home.near.list": "הקווים הקרובים אליך",
  "home.savedLine.from": "{minutes} דק׳ · מ{stop}",
  "home.savedLine.fromOnly": "מ{stop}",

  // Search (board 2): one list of places, stops and lines.
  "search.lines.more": "עוד {count} קווים",
  "search.lines.moreMany": "עוד יותר מ־{count} קווים",
  "search.line.near": "עוצר {minutes} דק׳ הליכה ממך",
  "search.stop.departures": "לוח היציאות של {stop}",
  "search.lines.unavailable": "חיפוש הקווים לא זמין כרגע",
} as const;
