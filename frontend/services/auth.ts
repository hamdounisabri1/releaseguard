import { api, unwrap } from "@/services/api";
import type { components } from "@/types/api";

export type Me = components["schemas"]["MeResponse"];

/** The signed-in user, their workspace and role; rejects with a 401 `ApiError` (and redirects) without a session. */
export function fetchMe(): Promise<Me> {
  return unwrap(api.GET("/api/v1/auth/me"));
}

export const meQueryKey = ["auth", "me"] as const;
