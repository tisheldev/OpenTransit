import { useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import type { NearbyDepartures } from "../../api/schemas";
import type { Departure } from "../stop/lines";

// Departures on Search's stop rows (client design, "Calls made by this session": shown only
// for stops already covered by the nearby-departures answer Home holds; there is no request
// per row). Read from the query cache, never fetched here.

/** Each stop's departures from every nearby answer in the cache, by stop id. */
export function useHeldNearbyDepartures(): Map<string, Departure[]> {
  const client = useQueryClient();
  const queries = client.getQueryCache().findAll({ queryKey: ["departures", "nearby"] });
  // A new array every render: its content changes only when an answer's time does.
  const signature = queries.map((query) => `${query.queryHash}@${query.state.dataUpdatedAt}`).join("|");
  return useMemo(() => {
    const byStop = new Map<string, Departure[]>();
    for (const query of queries) {
      const data = query.state.data as NearbyDepartures | undefined;
      for (const entry of data?.data ?? []) {
        if (entry.departuresState !== "available" || !entry.departures) continue;
        byStop.set(entry.stop.stopId, entry.departures);
      }
    }
    return byStop;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `queries` is rebuilt every render; `signature` holds what matters.
  }, [signature]);
}
