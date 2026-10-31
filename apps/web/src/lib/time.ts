// Every time is Asia/Jerusalem with an explicit offset (design: Cross-cutting rules, Time).
// Nothing here reads the host's zone; tests run under a UTC host to prove it.
// The DST logic follows the API playground (services/api/.../playground/time.mjs).

export const ZONE = "Asia/Jerusalem";
export type Lang = "he" | "en";

const wallFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const offsetFormat = new Intl.DateTimeFormat("en-GB", { timeZone: ZONE, timeZoneName: "longOffset" });

function wallParts(date: Date): Record<string, string> {
  return Object.fromEntries(wallFormat.formatToParts(date).map((part) => [part.type, part.value]));
}

/** Israel wall-clock time as `YYYY-MM-DDTHH:mm`. */
export function israelWallTime(date: Date = new Date()): string {
  const p = wallParts(date);
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

/** Israel's UTC offset at an instant, as `+03:00` or `+02:00`. */
export function israelOffset(date: Date): string {
  const name = offsetFormat.formatToParts(date).find((part) => part.type === "timeZoneName")?.value ?? "GMT";
  const offset = name.replace("GMT", "");
  return offset === "" ? "+00:00" : offset;
}

/** An instant as an ISO string in Israel time with its explicit offset (an explicit "now"). */
export function toIsraelIso(date: Date = new Date()): string {
  const p = wallParts(date);
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}${israelOffset(date)}`;
}

export type DepartureInstant =
  | { ok: true; instant: string }
  | { ok: false; reason: "invalid" | "nonexistent" | "ambiguous" | "offset_mismatch"; candidates: string[] };

/**
 * Turn an Israel wall time (`YYYY-MM-DDTHH:mm`) into an instant with an explicit offset.
 * A time skipped by the spring change does not exist; a time repeated in autumn needs
 * the passenger to choose the offset. Both are checked against the timezone database.
 */
export function departureInstant(wall: string, offset: "auto" | "+03:00" | "+02:00" = "auto"): DepartureInstant {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(wall)) return { ok: false, reason: "invalid", candidates: [] };
  const candidates = ["+03:00", "+02:00"].filter((candidate) => {
    const date = new Date(`${wall}:00${candidate}`);
    return Number.isFinite(date.getTime()) && israelWallTime(date) === wall;
  });
  if (candidates.length === 0) {
    // Distinguish an impossible calendar value from a DST gap.
    const probe = new Date(`${wall}:00Z`);
    const valid = Number.isFinite(probe.getTime()) && probe.toISOString().slice(0, 16) === wall;
    return { ok: false, reason: valid ? "nonexistent" : "invalid", candidates };
  }
  if (offset !== "auto") {
    return candidates.includes(offset)
      ? { ok: true, instant: `${wall}:00${offset}` }
      : { ok: false, reason: "offset_mismatch", candidates };
  }
  if (candidates.length > 1) return { ok: false, reason: "ambiguous", candidates };
  return { ok: true, instant: `${wall}:00${candidates[0]}` };
}

/** 08:00 tomorrow on the Israel calendar, as a wall time. */
export function tomorrowMorning(date: Date = new Date()): string {
  const today = israelWallTime(date).slice(0, 10);
  const next = new Date(`${today}T12:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  return `${next.toISOString().slice(0, 10)}T08:00`;
}

/** Shift an instant by whole minutes (earlier/later), returning an explicit-offset ISO. */
export function shiftMinutes(instant: string, minutes: number): string {
  return toIsraelIso(new Date(Date.parse(instant) + minutes * 60_000));
}

const locales: Record<Lang, string> = { he: "he-IL", en: "en-GB" };

/** 24-hour clock time in Israel, e.g. `08:05`. */
export function formatClock(instant: string | Date, lang: Lang): string {
  return new Intl.DateTimeFormat(locales[lang], {
    timeZone: ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    numberingSystem: "latn",
  }).format(typeof instant === "string" ? new Date(instant) : instant);
}

/** Weekday and date in Israel, e.g. `Thu, 1 Oct` / `יום ה׳, 1 באוק׳`. */
export function formatDate(instant: string | Date, lang: Lang): string {
  return new Intl.DateTimeFormat(locales[lang], {
    timeZone: ZONE,
    weekday: "short",
    day: "numeric",
    month: "short",
    numberingSystem: "latn",
  }).format(typeof instant === "string" ? new Date(instant) : instant);
}

/** Whole minutes from `now` until `instant`, rounded up; negative once it has passed. */
export function minutesUntil(instant: string, now: Date = new Date()): number {
  return Math.ceil((Date.parse(instant) - now.getTime()) / 60_000);
}
