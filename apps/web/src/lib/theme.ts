import { useSyncExternalStore } from "react";
import { loadLocalState, updateLocalState } from "../storage/local";
import { DEFAULT_THEME, THEME_COLORS, type ThemeName } from "../styles/tokens";

// Colour theme. Dark is the default whatever the device prefers (user, 6 November 2026);
// light is a choice in Settings, kept in local settings. public/theme.js (generated with
// the tokens) applies the stored choice before first paint; this module keeps the
// document's data-theme and theme-color in step afterwards. color-scheme follows from
// data-theme in tokens.css.

export type { ThemeName };

export function storedTheme(): ThemeName {
  return loadLocalState().state.settings.theme ?? DEFAULT_THEME;
}

let current: ThemeName | undefined;
const listeners = new Set<() => void>();

/** Set data-theme and the theme-color meta (the browser's own bars) for a theme. */
export function applyTheme(theme: ThemeName, doc: Document = document): void {
  doc.documentElement.setAttribute("data-theme", theme);
  doc.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[theme].bg);
}

export function getTheme(): ThemeName {
  current ??= storedTheme();
  return current;
}

/** Choose a theme (Settings): stored locally and applied at once. */
export function setTheme(theme: ThemeName): void {
  current = theme;
  updateLocalState((state) => ({ ...state, settings: { ...state.settings, theme } }));
  applyTheme(theme);
  for (const listener of listeners) listener();
}

/** Forget the in-memory choice (tests; clear all local data) and apply what is stored. */
export function resetTheme(): void {
  current = undefined;
  applyTheme(getTheme());
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTheme(): ThemeName {
  return useSyncExternalStore(subscribe, getTheme, getTheme);
}
