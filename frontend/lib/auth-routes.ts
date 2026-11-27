/**
 * Route constants for sign-in, shared by `proxy.ts`, the API client and the login form. Kept
 * free of imports so the proxy bundle stays small.
 */

export const LOGIN_PATH = "/login";
export const DEFAULT_AFTER_LOGIN = "/dashboard";

/**
 * The backend's session cookie (`app/services/auth_service.py`). It's HttpOnly: the frontend only
 * ever checks that it exists (in `proxy.ts`), never reads its value.
 */
export const SESSION_COOKIE = "rg_session";

// Any origin works: only used to check that a path resolves to the same origin.
const PROBE_ORIGIN = "http://releaseguard.invalid";

/** A path a browser or router would read as another host: `//host` or `/\host`. */
function isProtocolRelative(path: string): boolean {
  return path.startsWith("//") || path.startsWith("/\\");
}

/**
 * Where to go after signing in: the `next` query value when it's a path on this site, otherwise
 * the dashboard. Refuses absolute URLs, protocol-relative `//host` and `/\host` (browsers read a
 * backslash as a slash), so `?next=` can't become an open redirect, and the login page itself,
 * so it can't loop.
 *
 * The checks run on the input **and** on the normalized result: URL parsing collapses dot
 * segments, so `/..//evil.example` (or `/%2e%2e//evil.example`) comes out as `//evil.example`.
 */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith("/") || isProtocolRelative(raw)) return DEFAULT_AFTER_LOGIN;
  let url: URL;
  try {
    url = new URL(raw, PROBE_ORIGIN);
  } catch {
    return DEFAULT_AFTER_LOGIN;
  }
  if (url.origin !== PROBE_ORIGIN) return DEFAULT_AFTER_LOGIN;
  if (url.pathname === LOGIN_PATH || url.pathname.startsWith(`${LOGIN_PATH}/`)) {
    return DEFAULT_AFTER_LOGIN;
  }
  const path = `${url.pathname}${url.search}${url.hash}`;
  if (isProtocolRelative(path) || path.includes("\\")) return DEFAULT_AFTER_LOGIN;
  return path;
}
