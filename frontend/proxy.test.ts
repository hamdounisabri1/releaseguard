import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { config, proxy } from "@/proxy";

function request(path: string, cookie?: string) {
  return new NextRequest(`http://localhost:3000${path}`, {
    headers: cookie ? { cookie } : undefined,
  });
}

describe("proxy", () => {
  it("sends a visitor without a session cookie to the login page, remembering the path", () => {
    const response = proxy(request("/applications?tab=all"));

    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("location") ?? "");
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("next")).toBe("/applications?tab=all");
  });

  it("lets a request with a session cookie through (AuthGuard validates it)", () => {
    const response = proxy(request("/dashboard", "rg_session=abc"));
    expect(response.headers.get("location")).toBeNull();
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("never redirects the login page itself", () => {
    const response = proxy(request("/login?next=%2Fdashboard"));
    expect(response.headers.get("location")).toBeNull();
  });

  it("ignores other cookies", () => {
    expect(proxy(request("/dashboard", "theme=dark")).status).toBe(307);
  });
});

describe("proxy matcher", () => {
  // Same pattern as `config.matcher`, compiled the way Next compiles a negative-lookahead matcher.
  const pattern = new RegExp(`^${config.matcher[0]}$`);

  it.each(["/dashboard", "/login-help", "/loginx", "/icon.svgx", "/"])("checks %s", (path) => {
    expect(pattern.test(path)).toBe(true);
  });

  it.each([
    "/login",
    "/login/",
    "/_next/static/chunk.js",
    "/icon.svg",
    "/favicon.ico",
    "/api/v1/x",
  ])("skips %s", (path) => {
    expect(pattern.test(path)).toBe(false);
  });
});
