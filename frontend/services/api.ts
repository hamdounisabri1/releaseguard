import createClient, { type Middleware } from "openapi-fetch";

import { apiBaseUrl } from "@/lib/env";
import type { components, paths } from "@/types/api";

/** The backend's single error shape: `{"error": {"code", "message", "details"}}`. */
export type ErrorResponse = components["schemas"]["ErrorResponse"];

/** A failed API call. `code` is the backend's machine-readable error code (`not_found`, …). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const LOGIN_PATH = "/login";

/**
 * The generated paths already start with `/api/v1`, so the client's base URL is what comes
 * before it: `""` (same origin behind Caddy) or `http://localhost:8000` in local dev.
 */
export const apiOrigin = apiBaseUrl.replace(/\/api\/v1\/?$/, "");

function isErrorResponse(body: unknown): body is ErrorResponse {
  if (typeof body !== "object" || body === null || !("error" in body)) return false;
  const error = (body as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

/** Builds an `ApiError` from a failed response body (parsed JSON, raw text or nothing). */
export function toApiError(status: number, body: unknown, statusText = ""): ApiError {
  if (isErrorResponse(body)) {
    return new ApiError(status, body.error.code, body.error.message, body.error.details ?? {});
  }
  return new ApiError(
    status,
    "unknown_error",
    statusText ? `Request failed: ${status} ${statusText}` : `Request failed: ${status}`,
  );
}

/**
 * Sends the browser to the login page, remembering where it was (no-op on the server). A full
 * page load drops every cached query of the old session; `replace` keeps Back from returning
 * to the page that just failed.
 */
export function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const { pathname, search } = window.location;
  if (pathname === LOGIN_PATH) return; // a failed login is a 401 too; stay on the form
  window.location.replace(`${LOGIN_PATH}?next=${encodeURIComponent(pathname + search)}`);
}

/** A 401 means no session or an expired one (`session_expired`): go to the login page. */
const redirectOn401: Middleware = {
  onResponse({ response }) {
    if (response.status === 401) redirectToLogin();
    return undefined;
  },
};

/**
 * Typed client for every backend route. The session is an `HttpOnly` cookie, so requests only
 * need `credentials: "include"` (also covers local dev, where the API is on another port).
 */
export const api = createClient<paths>({
  baseUrl: apiOrigin,
  credentials: "include",
  // Looked up per call rather than captured at import, so tests can stub `fetch`. openapi-fetch
  // also passes its `requestInitExt` (e.g. an undici dispatcher) as a second argument; its type
  // declares only the first, so forward everything through a rest parameter.
  fetch: ((...args: Parameters<typeof fetch>) => globalThis.fetch(...args)) as (
    input: Request,
  ) => Promise<Response>,
});
api.use(redirectOn401);

type ClientResult<T> = { data?: T; error?: unknown; response: Response };

/**
 * Awaits an `api.GET/POST/…` call and returns its data, or throws an `ApiError`, so TanStack
 * Query sees failures as errors: `queryFn: () => unwrap(api.GET("/api/v1/auth/me"))`.
 */
export async function unwrap<T>(request: Promise<ClientResult<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok) throw toApiError(response.status, error, response.statusText);
  return data as T;
}
