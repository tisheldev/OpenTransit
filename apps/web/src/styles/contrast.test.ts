import { describe, expect, it } from "vitest";
import { THEME_COLORS, THEMES, type ColorToken } from "./tokens";

// The colour pairs the design system's token notes promise, checked in both themes (WCAG
// 2.2 AA: 4.5:1 for text, 3:1 for focus rings, control boundaries and large or bold text).

function luminance(hex: string): number {
  const channel = (offset: number) => {
    const c = parseInt(hex.slice(1 + offset, 3 + offset), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
}

function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

type Pair = [ColorToken, ColorToken];

const TEXT: Pair[] = [
  ["ink", "bg"],
  ["ink", "surface"],
  ["ink", "surface-sunken"],
  ["ink", "brand-tint"],
  ["ink-muted", "bg"],
  ["ink-muted", "surface"],
  ["ink-muted", "surface-sunken"],
  ["ink-subtle", "surface"],
  ["brand", "bg"],
  ["brand", "surface"],
  ["brand-strong", "brand-tint"],
  ["on-brand", "brand"],
  ["on-brand", "brand-strong"],
  // The main button (look of 11 November 2026: never white).
  ["on-action", "action"],
  ["on-action", "action-pressed"],
  ["on-brand", "destination"],
  ["on-brand", "mode-bus"],
  ["on-brand", "mode-rail"],
  ["link", "bg"],
  ["link", "surface"],
  ["destination", "surface"],
  ["mode-walk", "surface"],
  ["mode-rail", "mode-rail-tint"],
  ["status-scheduled", "surface-sunken"],
  ["status-live", "surface"],
  ["status-late", "surface"],
  ["status-cancelled", "surface"],
  ["status-cancelled", "error-bg"],
  ["success", "surface"],
  ["warning-ink", "warning-bg"],
  ["on-hero", "hero"],
  ["on-hero-muted", "hero"],
  ["hero-accent", "hero"],
];

const NON_TEXT: Pair[] = [
  ["focus", "bg"],
  ["focus", "surface"],
  ["border-strong", "bg"],
  ["border-strong", "surface"],
];

// Kept from the source palette but restricted by the token notes: mode-bus on its tint is
// for icons and bold 14 px+ only; ink-subtle is for surface only (use ink-muted on bg).
const RESTRICTED: Pair[] = [
  ["mode-bus", "mode-bus-tint"],
  ["ink-subtle", "bg"],
];

describe.each(THEMES)("%s theme contrast", (theme) => {
  const colours = THEME_COLORS[theme];
  it.each(TEXT)("text %s on %s ≥ 4.5:1", (fg, bg) => {
    expect(contrast(colours[fg], colours[bg])).toBeGreaterThanOrEqual(4.5);
  });
  it.each(NON_TEXT)("%s on %s ≥ 3:1", (fg, bg) => {
    expect(contrast(colours[fg], colours[bg])).toBeGreaterThanOrEqual(3);
  });
  it.each(RESTRICTED)("restricted %s on %s still ≥ 3:1 (large or bold only)", (fg, bg) => {
    expect(contrast(colours[fg], colours[bg])).toBeGreaterThanOrEqual(3);
  });
});
