import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { signOut } from "@/components/auth/account-menu";

vi.mock("@/lib/env", () => ({ apiBaseUrl: "http://api.test/api/v1" }));

const replace = vi.fn();

function respond(status: number) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      status === 0
        ? Promise.reject(new TypeError("Failed to fetch"))
        : new Response(
            status === 204
              ? null
              : JSON.stringify({ error: { code: "x", message: "x", details: {} } }),
            { status, headers: { "Content-Type": "application/json" } },
          ),
    ),
  );
}

beforeEach(() => {
  replace.mockReset();
  vi.stubGlobal("window", { location: { pathname: "/dashboard", search: "", replace } });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("signOut", () => {
  it("loads the login page after the backend ends the session", async () => {
    respond(204);
    expect(await signOut()).toBe(true);
    expect(replace).toHaveBeenLastCalledWith("/login");
  });

  it("treats a 401 (session already gone) as signed out", async () => {
    respond(401);
    expect(await signOut()).toBe(true);
    expect(replace).toHaveBeenLastCalledWith("/login");
  });

  it.each([
    [503, "a server error"],
    [403, "a refused Origin"],
    [0, "a network error"],
  ])("stays on the page after %s (%s): the session is still alive", async (status) => {
    respond(status);
    expect(await signOut()).toBe(false);
    expect(replace).not.toHaveBeenCalled();
  });
});
