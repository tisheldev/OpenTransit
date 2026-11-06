// The departure that the @real e2e specs and the fixture recorder plan with. Never a
// literal date: those go stale as soon as the API serves a newer generation (a 2 November
// departure got a correct 422 from the 6 November generation). Instead: the first day after
// today on the Israel calendar that is a working day (Sunday to Thursday, or the weekday
// asked for) and whose clock time, Israel time, lies inside the API's coverage.

const ZONE = "Asia/Jerusalem";
const DAY_MS = 86_400_000;

/** Israel's UTC offset ("+02:00" or "+03:00") at an instant. */
function israelOffset(instant) {
  const name = new Intl.DateTimeFormat("en-US", { timeZone: ZONE, timeZoneName: "longOffset" })
    .formatToParts(instant)
    .find((part) => part.type === "timeZoneName").value;
  return name === "GMT" ? "+00:00" : name.replace("GMT", "");
}

/**
 * @param {{ from: string, until: string }} coverage  `meta.coverage` from GET /v1/status
 * @param {{ clock?: string, weekday?: number | null, marginHours?: number, now?: Date }} [options]
 *   clock "HH:MM" Israel time (default 08:00); weekday 0–6 (Sunday = 0) or null for any
 *   working day; marginHours of coverage left after the departure (default 6).
 * @returns {{ date: string, wall: string, departAt: string } | null}
 */
export function departureInCoverage(coverage, { clock = "08:00", weekday = null, marginHours = 6, now = new Date() } = {}) {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: ZONE }).format(now);
  const from = Date.parse(coverage.from);
  const until = Date.parse(coverage.until);
  for (let days = 1; days <= 62; days += 1) {
    const day = new Date(Date.parse(`${today}T12:00:00Z`) + days * DAY_MS);
    const dow = day.getUTCDay();
    if (weekday === null ? dow === 5 || dow === 6 : dow !== weekday) continue;
    const date = day.toISOString().slice(0, 10);
    const departAt = `${date}T${clock}:00${israelOffset(new Date(`${date}T${clock}:00Z`))}`;
    const at = Date.parse(departAt);
    if (at < from || at + marginHours * 3_600_000 > until) continue;
    return { date, wall: `${date}T${clock}`, departAt };
  }
  return null;
}
