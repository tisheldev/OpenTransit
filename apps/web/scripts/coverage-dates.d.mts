export interface Coverage {
  from: string;
  until: string;
}

export interface Departure {
  /** Israel calendar date, YYYY-MM-DD. */
  date: string;
  /** Wall-clock time for the plan draft, YYYY-MM-DDTHH:MM (Israel). */
  wall: string;
  /** ISO 8601 with Israel's offset, for POST /v1/journeys. */
  departAt: string;
}

export function departureInCoverage(
  coverage: Coverage,
  options?: { clock?: string; weekday?: number | null; marginHours?: number; now?: Date },
): Departure | null;
