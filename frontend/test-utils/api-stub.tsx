import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { vi } from "vitest";

import { makeQueryClient } from "@/lib/query-client";
import type { components } from "@/types/api";

export type Reply = { status: number; body?: unknown };
export type Routes = Record<string, Reply | ((request: Request) => Reply | Promise<Reply>)>;

/**
 * Stubs `fetch` with replies keyed by "METHOD /path" (no query string); an unknown route throws.
 * Returns the mock, whose calls hold the `Request`s sent. Pair with
 * `vi.mock("@/lib/env", () => ({ apiBaseUrl: "http://api.test/api/v1" }))`.
 */
export function stubApi(routes: Routes) {
  const fetchMock = vi.fn(async (input: Request) => {
    const key = `${input.method} ${new URL(input.url).pathname}`;
    const route = routes[key];
    if (!route) throw new Error(`unexpected request ${key}`);
    const { status, body } = typeof route === "function" ? await route(input) : route;
    return new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The `Request`s sent to `METHOD /path`, in order. */
export function requestsTo(fetchMock: ReturnType<typeof stubApi>, key: string): Request[] {
  return fetchMock.mock.calls
    .map(([request]) => request)
    .filter((request) => `${request.method} ${new URL(request.url).pathname}` === key);
}

export function errorReply(
  status: number,
  code: string,
  message = "Refused.",
  details = {},
): Reply {
  return { status, body: { error: { code, message, details } } };
}

export function meReply(role: components["schemas"]["Role"]): Reply {
  return {
    status: 200,
    body: {
      user: { id: "u1", email: `${role}@acme.test`, display_name: `Test ${role}` },
      workspace: { id: "w1", name: "Acme", slug: "acme" },
      role,
    },
  };
}

export function renderWithClient(ui: React.ReactNode) {
  return render(<QueryClientProvider client={makeQueryClient()}>{ui}</QueryClientProvider>);
}
