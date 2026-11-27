import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/services/api";
import type { Environment } from "@/services/applications";
import type { components } from "@/types/api";

export type EnvironmentUpdate = components["schemas"]["EnvironmentUpdate"];

/** One environment; 404 for an unknown id or another workspace's. */
export function fetchEnvironment(environmentId: string): Promise<Environment> {
  return unwrap(
    api.GET("/api/v1/environments/{environment_id}", {
      params: { path: { environment_id: environmentId } },
    }),
  );
}

export function environmentQueryKey(environmentId: string) {
  return ["environments", environmentId] as const;
}

export function environmentQueryOptions(environmentId: string) {
  return queryOptions({
    queryKey: environmentQueryKey(environmentId),
    queryFn: () => fetchEnvironment(environmentId),
  });
}

/**
 * Changes health-check timing and the verification rule (Admin only). Only the fields sent
 * change. Fails with 403 for other roles or 422 `validation_error` (out-of-range values).
 */
export function updateEnvironment(
  environmentId: string,
  body: EnvironmentUpdate,
): Promise<Environment> {
  return unwrap(
    api.PATCH("/api/v1/environments/{environment_id}", {
      params: { path: { environment_id: environmentId } },
      body,
    }),
  );
}
