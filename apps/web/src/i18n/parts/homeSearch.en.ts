import type { he_homeSearch } from "./homeSearch.he";

// English mirror of homeSearch.he.ts (same keys and placeholders).
export const en_homeSearch: Record<keyof typeof he_homeSearch, string> = {
  "screen.line": "Line",

  "home.search.hint": "Place, stop or line",
  "home.near.title": "Near you",
  "home.near.walk": "Up to {minutes} min walk",
  "home.near.from": "{stop} · {minutes} min walk",
  "home.near.none": "No lines leave the stops near you in the next hour.",
  "home.near.list": "Lines near you",
  "home.savedLine.from": "{minutes} min · from {stop}",
  "home.savedLine.fromOnly": "From {stop}",

  "search.lines.more": "{count} more lines",
  "search.lines.moreMany": "More than {count} more lines",
  "search.line.near": "Stops a {minutes} min walk from you",
  "search.stop.departures": "Departures from {stop}",
  "search.lines.unavailable": "Line search is unavailable right now",
};
