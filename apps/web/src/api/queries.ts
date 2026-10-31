import { QueryClient, useQuery } from "@tanstack/react-query";
import { isRetryable } from "./classify";
import { getStatus } from "./endpoints";
import { ApiFailure, unwrap } from "./result";

export const queryKeys = {
  status: ["status"] as const,
};

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // One retry for transient failures; 429 is handled by the screen honouring Retry-After.
        retry: (count, error) =>
          count < 1 && error instanceof ApiFailure && isRetryable(error.state) && error.state !== "rate_limited",
        refetchOnWindowFocus: false,
      },
    },
  });
}

/** Data status for the home banner (design: Screens, cached 5 minutes). */
export function useStatus() {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: async ({ signal }) => unwrap(await getStatus(signal)),
    staleTime: 5 * 60_000,
  });
}
