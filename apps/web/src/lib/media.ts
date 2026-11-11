import { useSyncExternalStore } from "react";

/** The wide-screen layout (board 8, user 11 November 2026): the panel beside the map. Same breakpoint as shell.css. */
export const WIDE_QUERY = "(min-width: 900px)";

function matches(query: string): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(query).matches;
}

/** Whether a media query matches now (false where matchMedia is missing, as in some tests). */
export function isMedia(query: string): boolean {
  return matches(query);
}

/** A media query's current answer, re-rendering when it changes. */
export function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => matches(query),
    () => false,
  );
}
