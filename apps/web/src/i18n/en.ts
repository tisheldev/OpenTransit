import type { MessageKey } from "./he";
import { en_compare } from "./parts/compare.en";
import { en_map } from "./parts/map.en";
import { en_nav } from "./parts/nav.en";
import { en_secondary } from "./parts/secondary.en";
import { en_shell } from "./parts/shell.en";

// Mirrors he.ts key for key; the type rejects a missing or extra key.
const core = {
  "app.name": "OpenTransit",
  "app.tagline": "Plan and navigate public transport",
  "app.skipToContent": "Skip to content",

  "screen.home": "Home",
  "screen.search": "Where to?",
  "screen.compare": "Compare options",
  "screen.route": "Route details",
  "screen.navigate": "Navigate",
  "screen.stop": "Stop",
  "screen.trip": "Trip",
  "screen.nearby": "Nearby stops",
  "screen.lines": "Lines",
  "screen.settings": "Settings",
  "screen.notFound": "Page not found",
  "screen.placeholder": "This screen is not built yet.",
  "screen.backHome": "Back to home",

  "nav.back": "Back",
  "nav.locate": "My location",

  "settings.language": "Language",
  "settings.language.he": "עברית",
  "settings.language.en": "English",
  "settings.clearData": "Clear all local data",
  "settings.clearData.confirm": "Delete saved places, recent searches and settings from this device?",
  "settings.clearData.done": "Local data cleared.",

  "status.checking": "Checking data status…",
  "status.ready": "Timetable available",
  "status.coverage": "Scheduled timetable from {from} to {until}",
  "status.notReady": "Planning is unavailable right now",

  "banner.testData": "Test data — not the real timetable",
  "banner.staleData": "The timetable has not been refreshed recently and may be out of date",
  "banner.liveUnavailable": "Live times and alerts unavailable",

  "time.scheduled": "Scheduled",
  "time.now": "Now",
  "time.departAt": "Depart at",
  "time.arriveBy": "Arrive by",

  "state.loading": "Loading…",
  "state.retry": "Try again",
  "state.retryIn": "You can try again in {seconds} s",
  "state.empty.noRoute": "No route at this time. Try another time or a nearby point.",
  "state.empty.noDepartures": "No scheduled departures in this window.",
  "state.empty.noMatches": "No results. Try different wording.",
  "state.unavailable.live": "Live times and alerts unavailable",
  "state.unavailable.category": "Some result types are unavailable right now: {categories}",

  "error.outside_window": "That time is outside the timetable. Choose between {from} and {until}.",
  "error.outside_window.noDates": "That time is outside the timetable.",
  "error.invalid_place_ref": "The saved place is no longer recognised. Retrying with its location.",
  "error.invalid_cursor": "The list changed. Reloading it from the start.",
  "error.invalid_request": "The request was not accepted. Try again.",
  "error.not_found": "No longer in the timetable.",
  "error.rate_limited": "Too many requests. Wait a moment and try again.",
  "error.data_expired": "The timetable needs an update and is unavailable right now.",
  "error.category_unavailable": "Searching this type is unavailable right now.",
  "error.temporarily_unavailable": "Temporarily unavailable.",
  "error.network": "Can't reach OpenTransit. Check your internet connection.",
  "error.unexpected": "Something went wrong. Try again.",

  "place.stop": "Stop",
  "place.station": "Station",
  "place.poi": "Place",
  "place.address": "Address",
};

export const en: Record<MessageKey, string> = { ...core, ...en_map, ...en_shell, ...en_compare, ...en_nav, ...en_secondary };
