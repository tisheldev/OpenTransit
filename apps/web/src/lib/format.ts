import type { Lang } from "./time";

// Units from the design: דק׳ (min), שע׳ (h), מ׳ (m), ק״מ (km). Digits stay Latin; the
// caller wraps the result in <bdi> so it reads correctly inside RTL text.

const units = {
  he: { min: "דק׳", h: "שע׳", m: "מ׳", km: "ק״מ" },
  en: { min: "min", h: "h", m: "m", km: "km" },
} as const;

const number = (lang: Lang, digits = 0) =>
  new Intl.NumberFormat(lang === "he" ? "he-IL" : "en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
    numberingSystem: "latn",
  });

/** Duration rounded up to whole minutes: `12 דק׳`, `1 שע׳ 5 דק׳`. */
export function formatDuration(seconds: number, lang: Lang): string {
  const minutes = Math.max(0, Math.ceil(seconds / 60));
  const u = units[lang];
  if (minutes < 60) return `${minutes} ${u.min}`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} ${u.h}` : `${hours} ${u.h} ${rest} ${u.min}`;
}

/**
 * Walking distance, or null when the API does not know it (a transfer whose street path
 * is unavailable): the caller then shows a time-only walk instead of inventing one.
 */
export function formatDistance(meters: number | null, lang: Lang): string | null {
  if (meters === null || !Number.isFinite(meters)) return null;
  const u = units[lang];
  if (meters < 1000) return `${number(lang).format(Math.max(10, Math.round(meters / 10) * 10))} ${u.m}`;
  return `${number(lang, 1).format(meters / 1000)} ${u.km}`;
}
