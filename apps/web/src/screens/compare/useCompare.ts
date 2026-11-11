import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useMemo, useState, type RefObject } from "react";
import { getStatus } from "../../api/endpoints";
import { queryKeys } from "../../api/queries";
import { ApiFailure, unwrap } from "../../api/result";
import type { Trip } from "../../api/schemas";
import type { Journey } from "../../api/types";
import { useI18n } from "../../i18n/I18nProvider";
import { sameJourney, startActiveTrip, useActiveTrip } from "../../nav/activeTrip";
import { usePlan } from "../../plan/PlanProvider";
import { cachedTrips, MARK_PAINTED, MARK_REQUEST, useJourneyRequest, useJourneys, useTrips } from "../../plan/queries";
import { go } from "../../router";
import { endpointLabel, israelDate, type EndLabels } from "./labels";

// The plan answer both Compare steps read (board Choose and board Step): the same query
// (one request; the details step reuses the cached answer), the chosen option, its trip
// details for stop counts, and the start-navigation contract.

export type TripState = { status: "pending" } | { status: "error" } | { status: "ok"; trip: Trip["data"] };

const tripRefsOf = (journey: Journey | undefined) =>
  journey ? journey.legs.flatMap((leg) => (leg.transit ? [leg.transit.engineTripId] : [])) : [];

/** Coverage for OUTSIDE_SERVICE_WINDOW: the problem has none, so it comes from /v1/status. */
function useCoverage(enabled: boolean) {
  const status = useQuery({
    queryKey: queryKeys.status,
    queryFn: async ({ signal }) => unwrap(await getStatus(signal)),
    staleTime: 5 * 60_000,
    enabled,
  });
  const meta = status.data?.meta as { coverage?: { from: string; until: string } } | undefined;
  return meta?.coverage ?? null;
}

/** The device clock, refreshed every 30 s, for "בעוד 4 דק׳". */
export function useNow(intervalMs = 30_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

/**
 * The scroll container's own padding, so the pinned bottom bar can reach its edges
 * (full width, flush with the bottom) whatever the sheet's padding is.
 */
export function useScrollPadding(ref: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element || typeof getComputedStyle === "undefined") return;
    let parent = element.parentElement;
    while (parent && !/(auto|scroll)/.test(getComputedStyle(parent).overflowY)) parent = parent.parentElement;
    if (!parent) return;
    const style = getComputedStyle(parent);
    element.style.setProperty("--compare-pad-end", style.paddingBlockEnd || style.paddingBottom || "0px");
    element.style.setProperty("--compare-pad-inline", style.paddingInlineStart || style.paddingLeft || "0px");
  }, [ref]);
}

export function useCompare() {
  const { t, lang } = useI18n();
  const plan = usePlan();
  const { draft, selected, setSelected } = plan;
  const client = useQueryClient();
  const [attempt, setAttempt] = useState(0);

  const ends: EndLabels = useMemo(
    () => ({ from: endpointLabel(draft.from, t), to: endpointLabel(draft.to, t) }),
    [draft.from, draft.to, t],
  );

  const built = useJourneyRequest(draft, lang, null, attempt);
  const result = built.data;
  const planned = result?.ok ? result : null;
  const journeys = useJourneys(planned);
  const answer = journeys.data;
  const list = useMemo(() => answer?.response.data.journeys ?? [], [answer]);
  const index = Math.min(selected, Math.max(0, list.length - 1));
  const chosen: Journey | undefined = list[index];
  // The previous time's answer, shown until the new one arrives (same ends only).
  const refreshing = built.isPlaceholderData || journeys.isPlaceholderData;

  // Trip details for the chosen option only, fetched once the options are on screen.
  const refs = useMemo(() => tripRefsOf(chosen), [chosen]);
  const tripQueries = useTrips(refs, chosen !== undefined);
  const trips: Record<string, TripState> = {};
  refs.forEach((ref, i) => {
    const query = tripQueries[i];
    trips[ref] = query?.data ? { status: "ok", trip: query.data.data } : query?.isError ? { status: "error" } : { status: "pending" };
  });

  // SP04 client work: request sent → options painted (read by the @real test).
  useEffect(() => {
    if (!answer || typeof performance === "undefined" || !performance.getEntriesByName(MARK_REQUEST).length) return;
    performance.mark(MARK_PAINTED);
    try {
      performance.measure("ot:journeys:client", MARK_REQUEST, MARK_PAINTED);
    } catch {
      // marks cleared: nothing to measure
    }
  }, [answer]);

  const failure = journeys.error instanceof ApiFailure ? journeys.error : null;
  const coverage = useCoverage(failure?.state === "outside_window");

  const active = useActiveTrip();
  const resume = active !== null && chosen !== undefined && sameJourney(active.journey, chosen);
  /** Start navigation on the chosen option (or resume it), then open Navigate. */
  const start = () => {
    if (!chosen || !answer) return;
    if (!resume) startActiveTrip({ journey: chosen, meta: answer.response.meta, trips: cachedTrips(client, refs) });
    go({ name: "navigate" });
  };

  // The day the request asked about: options on another day name it.
  const asked = answer?.sent.departAt ?? answer?.sent.arriveBy ?? null;
  const askedDate = asked ? israelDate(asked) : israelDate(new Date());

  return {
    plan,
    ends,
    built,
    result,
    planned,
    journeys,
    answer,
    list,
    index,
    chosen,
    choose: setSelected,
    refreshing,
    trips,
    failure,
    coverage,
    retryLocation: () => setAttempt((n) => n + 1),
    start,
    resume,
    askedDate,
  };
}
