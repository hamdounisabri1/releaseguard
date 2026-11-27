import { type NextRequest, NextResponse } from "next/server";

import { LOGIN_PATH, SESSION_COOKIE } from "@/lib/auth-routes";

/**
 * Optimistic auth check (Next 16 Proxy, formerly middleware): no session cookie → the login page,
 * remembering where the visitor was going. It only checks that the cookie exists; `AuthGuard`
 * validates the session with `GET /auth/me`, and the backend enforces every permission. No
 * backend call and no secrets here.
 */
export function proxy(request: NextRequest): NextResponse {
  const { pathname, search } = request.nextUrl;
  // The matcher already skips it; checked again so a matcher change can't cause a redirect loop.
  if (pathname === LOGIN_PATH || request.cookies.has(SESSION_COOKIE)) return NextResponse.next();

  const login = request.nextUrl.clone();
  login.pathname = LOGIN_PATH;
  login.search = "";
  login.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(login);
}

export const config = {
  // Every page except the login page, Next's assets and the icon. `/api` is the backend's
  // (Caddy routes it there in production), so it never reaches the proxy anyway.
  // Anchored, so `/login-help` or `/icon.svgx` still get the check.
  matcher: ["/((?!login(?:/|$)|api/|_next/static/|_next/image|icon\\.svg$|favicon\\.ico$).*)"],
};
