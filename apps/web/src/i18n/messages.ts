import { en } from "./en";
import { he, type MessageKey } from "./he";

export type Lang = "he" | "en";
export type { MessageKey };

export const LANGS: readonly Lang[] = ["he", "en"];
export const dictionaries: Record<Lang, Record<MessageKey, string>> = { he, en };

export function directionOf(lang: Lang): "rtl" | "ltr" {
  return lang === "he" ? "rtl" : "ltr";
}

export function placeholdersOf(message: string): string[] {
  return [...message.matchAll(/\{(\w+)\}/g)].map((match) => match[1]!).sort();
}

/** Look up a message and fill its {placeholders}. A missing value stays visible as {name}. */
export function translate(lang: Lang, key: MessageKey, values: Record<string, string | number> = {}): string {
  return dictionaries[lang][key].replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in values ? String(values[name]) : whole,
  );
}
