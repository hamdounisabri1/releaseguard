import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/services/api";

const MAX_RETRIES = 2;

/** A failure that may pass on a later attempt: network errors, 5xx and 429 (rate limited). */
export function isRetryable(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true;
  return error.status >= 500 || error.status === 429;
}

/** Retry retryable failures a couple of times; any other 4xx won't change on retry. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  return isRetryable(error) && failureCount < MAX_RETRIES;
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, staleTime: 30_000 },
      mutations: { retry: false },
    },
  });
}
