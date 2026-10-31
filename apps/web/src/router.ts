import { useSyncExternalStore } from "react";

// Hash routing: the fragment never reaches the server or its logs (design: Stack).
// No location or coordinates are ever placed in a route.

export type Route =
  | { name: "home" }
  | { name: "search" }
  | { name: "compare" }
  | { name: "route" }
  | { name: "navigate" }
  | { name: "stop"; stopId: string }
  | { name: "trip"; tripRef: string }
  | { name: "nearby" }
  | { name: "lines" }
  | { name: "settings" }
  | { name: "notFound"; path: string };

const STATIC = ["search", "compare", "route", "navigate", "nearby", "lines", "settings"] as const;

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#/, "") || "/";
  const segments = path.split("/").filter(Boolean);
  if (segments.length === 0) return { name: "home" };
  const [first, second, ...rest] = segments;
  if (rest.length === 0 && second === undefined && (STATIC as readonly string[]).includes(first!)) {
    return { name: first as (typeof STATIC)[number] };
  }
  if (rest.length === 0 && second !== undefined) {
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

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash, () => "");
  return parseHash(hash);
}
