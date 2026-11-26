import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { shouldRetry } from "@/lib/query-client";
import { ApiError, api, toApiError, unwrap } from "@/services/api";
import { fetchMe } from "@/services/auth";

// Node's Request needs an absolute URL; in the browser the default `/api/v1` is same-origin.
vi.mock("@/lib/env", () => ({ apiBaseUrl: "http://api.test/api/v1" }));

const replace = vi.fn();

function stubLocation(pathname: string, search = "") {
  vi.stubGlobal("window", { location: { pathname, search, replace } });
}

function respond(status: number, body: unknown, contentType = "application/json") {
  const fetchMock = vi.fn<(request: Request) => Promise<Response>>(
    async () =>
      new Response(typeof body === "string" ? body : JSON.stringify(body), {
        status,
        statusText: status === 502 ? "Bad Gateway" : "",
        headers: { "Content-Type": contentType },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const ME = {
  user: { id: "u1", email: "dev@example.com", display_name: "Dev" },
  workspace: { id: "w1", name: "Acme", slug: "acme" },
  role: "developer",
};

beforeEach(() => {
  replace.mockReset();
  stubLocation("/dashboard");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends the session cookie to the /api/v1 path and returns the parsed body", async () => {
    const fetchMock = respond(200, ME);

    await expect(fetchMe()).resolves.toEqual(ME);

    const request = fetchMock.mock.calls[0][0];
    expect(request.url).toBe("http://api.test/api/v1/auth/me");
    expect(request.credentials).toBe("include");
    expect(replace).not.toHaveBeenCalled();
  });

  it("turns the standard error shape into an ApiError", async () => {
    respond(403, { error: { code: "forbidden", message: "Not allowed", details: { a: 1 } } });

    const error = await fetchMe().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 403,
      code: "forbidden",
      message: "Not allowed",
      details: { a: 1 },
    });
  });

  it("falls back to unknown_error when the body isn't the error shape", async () => {
    respond(502, "<html>bad gateway</html>", "text/html");

    const error = await fetchMe().catch((e: unknown) => e);

    expect(error).toMatchObject({
      status: 502,
      code: "unknown_error",
      message: "Request failed: 502 Bad Gateway",
    });
  });

  it("redirects to the login page on a 401, keeping the current path", async () => {
    stubLocation("/applications", "?page=2");
    respond(401, { error: { code: "session_expired", message: "Session expired", details: {} } });

    const error = await fetchMe().catch((e: unknown) => e);

    expect(error).toMatchObject({ status: 401, code: "session_expired" });
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fapplications%3Fpage%3D2");
  });

  it("stays on the login page when the login itself returns 401", async () => {
    stubLocation("/login");
    respond(401, { error: { code: "invalid_credentials", message: "Invalid", details: {} } });

    await expect(
      unwrap(api.POST("/api/v1/auth/login", { body: { email: "a@b.c", password: "x" } })),
    ).rejects.toMatchObject({ code: "invalid_credentials" });
    expect(replace).not.toHaveBeenCalled();
  });

  it("does not redirect for other errors", async () => {
    respond(404, { error: { code: "not_found", message: "Not found", details: {} } });

    await expect(fetchMe()).rejects.toMatchObject({ status: 404 });
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("toApiError", () => {
  it("handles an empty body", () => {
    expect(toApiError(500, undefined)).toMatchObject({ code: "unknown_error", status: 500 });
  });

  it("ignores an error object without code and message", () => {
    expect(toApiError(400, { error: "nope" })).toMatchObject({ code: "unknown_error" });
  });
});

describe("shouldRetry", () => {
  it("never retries another 4xx", () => {
    expect(shouldRetry(0, new ApiError(404, "not_found", "x"))).toBe(false);
    expect(shouldRetry(0, new ApiError(409, "conflict", "x"))).toBe(false);
  });

  it("retries 5xx, 429 and network errors twice", () => {
    expect(shouldRetry(0, new ApiError(503, "unknown_error", "x"))).toBe(true);
    expect(shouldRetry(1, new ApiError(429, "too_many_attempts", "x"))).toBe(true);
    expect(shouldRetry(2, new ApiError(429, "too_many_attempts", "x"))).toBe(false);
    expect(shouldRetry(1, new TypeError("Failed to fetch"))).toBe(true);
    expect(shouldRetry(2, new TypeError("Failed to fetch"))).toBe(false);
  });
});
