import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/services/api";
import type { components } from "@/types/api";

export type Me = components["schemas"]["MeResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type Role = components["schemas"]["Role"];

/** The signed-in user, their workspace and role; rejects with a 401 `ApiError` (and redirects) without a session. */
export function fetchMe(): Promise<Me> {
  return unwrap(api.GET("/api/v1/auth/me"));
}

export const meQueryKey = ["auth", "me"] as const;

/** `useQuery(meQueryOptions)`: one cached `/auth/me` shared by the guard, top bar and pages. */
export const meQueryOptions = queryOptions({ queryKey: meQueryKey, queryFn: fetchMe });

/**
 * Signs in. The backend sets the `rg_session` cookie and returns the same body as `/auth/me`.
 * Fails with 401 `invalid_credentials`, 429 `too_many_attempts` or 422 `validation_error`.
 */
export function login(body: LoginRequest): Promise<Me> {
  return unwrap(api.POST("/api/v1/auth/login", { body }));
}

/** Signs out: the backend deletes the session and clears the cookie (204). */
export async function logout(): Promise<void> {
  await unwrap(api.POST("/api/v1/auth/logout"));
}

const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  reviewer: "Reviewer",
  developer: "Developer",
  viewer: "Viewer",
};

export function roleLabel(role: Role): string {
  return ROLE_LABELS[role];
}
