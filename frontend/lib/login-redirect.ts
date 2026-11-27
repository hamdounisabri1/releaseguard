/**
 * Loop breaker for the login page's "already signed in" redirect. The login page trusts
 * `GET /auth/me` (the API host's cookie) while `proxy.ts` trusts the cookie on the frontend's
 * host; when they disagree (frontend on 127.0.0.1, API on localhost, or a browser that drops the
 * `Secure` cookie on http) each would send the browser back to the other forever. The login page
 * marks each automatic redirect; `AuthGuard` clears the mark once an app page renders. A mark
 * that is still there when the login page loads again means the redirect bounced.
 *
 * Browser storage can be missing or throw (private mode, blocked site data): then there is no
 * loop protection, which is the behaviour without this file.
 */

const KEY = "rg:login-redirect-at";
const BOUNCE_WINDOW_MS = 10_000;

export function markLoginRedirect(now = Date.now()): void {
  try {
    sessionStorage.setItem(KEY, String(now));
  } catch {
    // Storage unavailable: no loop protection.
  }
}

export function clearLoginRedirect(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Storage unavailable.
  }
}

/** True when the login page redirected away moments ago and the visitor is back already. */
export function loginRedirectBounced(now = Date.now()): boolean {
  try {
    const at = Number(sessionStorage.getItem(KEY));
    return at > 0 && now - at < BOUNCE_WINDOW_MS;
  } catch {
    return false;
  }
}
