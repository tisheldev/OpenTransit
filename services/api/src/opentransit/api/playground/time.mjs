const zone = "Asia/Jerusalem";
const wallFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

export function israelWallTime(date = new Date()) {
  const p = Object.fromEntries(wallFormat.formatToParts(date).map(p => [p.type, p.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

export function tomorrowMorning(date = new Date()) {
  const today = israelWallTime(date).slice(0, 10);
  const next = new Date(`${today}T12:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  return `${next.toISOString().slice(0, 10)}T08:00`;
}

// Check both Israeli offsets against the browser's timezone database. This
// rejects nonexistent DST times and requires an explicit choice for repeated times.
export function departureInstant(wall, offset = "auto") {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(wall)) {
    throw new Error("Choose a valid departure date and time.");
  }
  const candidates = ["+03:00", "+02:00"].filter(candidate => {
    const date = new Date(`${wall}:00${candidate}`);
    return Number.isFinite(date.getTime()) && israelWallTime(date) === wall;
  });
  if (!candidates.length) {
    throw new Error("This Israel time does not exist. Choose another time outside the daylight-saving change.");
  }
  if (offset !== "auto") {
    if (!candidates.includes(offset)) throw new Error("That UTC offset does not match Israel time on this date.");
    return `${wall}:00${offset}`;
  }
  if (candidates.length > 1) {
    throw new Error("This Israel time occurs twice. Choose UTC +03:00 or +02:00 to specify which departure.");
  }
  return `${wall}:00${candidates[0]}`;
}

export function clockTime(instant) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: zone, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(new Date(instant));
}

export function dateLabel(instant) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: zone, weekday: "short", day: "numeric", month: "short", year: "numeric",
  }).format(new Date(instant));
}

export function duration(seconds) {
  const minutes = Math.ceil(seconds / 60);
  return minutes >= 60 ? `${Math.floor(minutes / 60)} hr ${minutes % 60} min` : `${minutes} min`;
}
