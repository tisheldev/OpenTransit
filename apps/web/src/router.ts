import { useSyncExternalStore } from "react";

// Hash routing: the fragment never reaches the server or its logs (design: Stack).
// No location or coordinates are ever placed in a route.

/** Which field Search fills: a journey end, or a saved place being set. */
export type SearchField = "from" | "to" | "home" | "work" | "favourite";
export const SEARCH_FIELDS: readonly SearchField[] = ["from", "to", "home", "work", "favourite"];

export type Route =
  | { name: "home" }
  | { name: "search"; field: SearchField }
  | { name: "compare" }
  | { name: "navigate" }
  | { name: "stop"; stopId: string }
  | { name: "trip"; tripRef: string }
  | { name: "nearby" }
  | { name: "lines" }
  | { name: "settings" }
  | { name: "notFound"; path: string };

const STATIC = ["compare", "navigate", "nearby", "lines", "settings"] as const;

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#/, "") || "/";
  const segments = path.split("/").filter(Boolean);
  if (segments.length === 0) return { name: "home" };
  const [first, second, ...rest] = segments;
  if (rest.length > 0) return { name: "notFound", path };
  if (second === undefined && (STATIC as readonly string[]).includes(first!)) {
    return { name: first as (typeof STATIC)[number] };
  }
  if (first === "search") {
    if (second === undefined) return { name: "search", field: "to" };
    if ((SEARCH_FIELDS as readonly string[]).includes(second)) return { name: "search", field: second as SearchField };
    return { name: "notFound", path };
  }
  if (second !== undefined) {
    try {
      if (first === "stop") return { name: "stop", stopId: decodeURIComponent(second) };
      if (first === "trip") return { name: "trip", tripRef: decodeURIComponent(second) };
    } catch {
      // malformed escape: not a route
    }
  }
  return { name: "notFound", path };
}

export function hrefFor(route: Route): string {
  switch (route.name) {
    case "home":
      return "#/";
    case "search":
      return `#/search/${route.field}`;
    case "stop":
      return `#/stop/${encodeURIComponent(route.stopId)}`;
    case "trip":
      return `#/trip/${encodeURIComponent(route.tripRef)}`;
    case "notFound":
      return `#${route.path}`;
    default:
      return `#/${route.name}`;
  }
}

/** Go to a route. `replace` swaps the current history entry (no extra Back step). */
export function go(route: Route, options: { replace?: boolean } = {}): void {
  const href = hrefFor(route);
  if (options.replace) {
    window.history.replaceState(window.history.state, "", href);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    window.location.hash = href;
  }
}

/**
 * Each history entry this app creates carries its depth, so Back knows whether there is
 * an in-app screen to return to, and the screen that opened it (`otOpener`, a hash), so a
 * screen such as Search can return to whatever opened it. A deep link or a reload starts
 * at depth 0 with no opener.
 */
interface EntryState {
  otDepth?: unknown;
  otOpener?: unknown;
}
let currentDepth = 0;
let lastHash = typeof window === "undefined" ? "" : window.location.hash;
function stampDepth(): void {
  const state = window.history.state as EntryState | null;
  const opener = lastHash;
  lastHash = window.location.hash;
  if (typeof state?.otDepth === "number") {
    currentDepth = state.otDepth;
    return;
  }
  currentDepth += 1;
  window.history.replaceState({ ...(state ?? {}), otDepth: currentDepth, otOpener: opener }, "");
}

/** Back one level (design: Surface; Back never asks). Without an in-app entry, go to `fallback`. */
export function back(fallback: Route = { name: "home" }): void {
  if (currentDepth > 0) window.history.back();
  else go(fallback, { replace: true });
}

/** The route that opened the current history entry; null for a deep link or a reload. */
export function openerRoute(): Route | null {
  if (typeof window === "undefined" || currentDepth === 0) return null;
  const opener = (window.history.state as EntryState | null)?.otOpener;
  return typeof opener === "string" ? parseHash(opener) : null;
}

function subscribe(onChange: () => void): () => void {
  const listener = () => {
    stampDepth();
    onChange();
  };
  window.addEventListener("hashchange", listener);
  return () => window.removeEventListener("hashchange", listener);
}

if (typeof window !== "undefined" && typeof window.history.state?.otDepth !== "number") {
  window.history.replaceState({ ...(window.history.state ?? {}), otDepth: 0 }, "");
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash, () => "");
  return parseHash(hash);
}
