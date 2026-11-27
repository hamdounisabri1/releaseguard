// @vitest-environment jsdom
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { initials } from "@/components/auth/account-menu";
import { AuthGuard } from "@/components/auth/auth-guard";
import { LoginForm } from "@/components/auth/login-form";
import { markLoginRedirect } from "@/lib/login-redirect";
import { makeQueryClient } from "@/lib/query-client";
import { meQueryKey } from "@/services/auth";

vi.mock("@/lib/env", () => ({ apiBaseUrl: "http://api.test/api/v1" }));

const routerReplace = vi.fn();
let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: routerReplace }),
  useSearchParams: () => searchParams,
}));

const ME = {
  user: { id: "u1", email: "admin@acme.test", display_name: "Ada Admin" },
  workspace: { id: "w1", name: "Acme", slug: "acme" },
  role: "admin",
};

type Reply = { status: number; body?: unknown };
type Routes = Record<string, Reply | (() => Reply)>;

/** Stubs `fetch` with replies keyed by "METHOD /path"; returns the mock to inspect calls. */
function stubApi(routes: Routes) {
  const fetchMock = vi.fn(async (input: Request) => {
    const key = `${input.method} ${new URL(input.url).pathname}`;
    const route = routes[key];
    if (!route) throw new Error(`unexpected request ${key}`);
    const { status, body } = typeof route === "function" ? route() : route;
    return new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const NO_SESSION: Reply = {
  status: 401,
  body: { error: { code: "not_authenticated", message: "Sign in.", details: {} } },
};

function renderWithClient(ui: React.ReactNode) {
  return render(<QueryClientProvider client={makeQueryClient()}>{ui}</QueryClientProvider>);
}

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

beforeEach(() => {
  routerReplace.mockReset();
  searchParams = new URLSearchParams();
  // The API client's 401 redirect is a no-op on the login page.
  window.history.replaceState({}, "", "/login");
  sessionStorage.clear();
});

afterEach(cleanup);

describe("LoginForm", () => {
  it("signs in and goes to the dashboard", async () => {
    const fetchMock = stubApi({
      "GET /api/v1/auth/me": NO_SESSION,
      "POST /api/v1/auth/login": { status: 200, body: ME },
    });
    renderWithClient(<LoginForm />);

    await fillAndSubmit("Admin@Acme.test ", "releaseguard-dev");

    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/dashboard"));
    const login = fetchMock.mock.calls
      .map(([request]) => request)
      .find((request) => request.method === "POST");
    expect(await login?.json()).toEqual({
      email: "Admin@Acme.test",
      password: "releaseguard-dev",
    });
  });

  it("goes to a same-site ?next= path after signing in", async () => {
    searchParams = new URLSearchParams({ next: "/approvals?env=prod" });
    stubApi({
      "GET /api/v1/auth/me": NO_SESSION,
      "POST /api/v1/auth/login": { status: 200, body: ME },
    });
    renderWithClient(<LoginForm />);

    await fillAndSubmit("admin@acme.test", "releaseguard-dev");

    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/approvals?env=prod"));
  });

  it("ignores an off-site ?next= (no open redirect)", async () => {
    searchParams = new URLSearchParams({ next: "//evil.example" });
    stubApi({
      "GET /api/v1/auth/me": NO_SESSION,
      "POST /api/v1/auth/login": { status: 200, body: ME },
    });
    renderWithClient(<LoginForm />);

    await fillAndSubmit("admin@acme.test", "releaseguard-dev");

    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows an error for bad credentials, clears the password and stays on the page", async () => {
    stubApi({
      "GET /api/v1/auth/me": NO_SESSION,
      "POST /api/v1/auth/login": {
        status: 401,
        body: { error: { code: "invalid_credentials", message: "Invalid.", details: {} } },
      },
    });
    renderWithClient(<LoginForm />);

    await fillAndSubmit("admin@acme.test", "wrong-password");

    const alert = await screen.findByText("Email or password is incorrect.");
    expect(alert.closest("[role=alert]")).toBe(document.activeElement);
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("");
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("shows the backend's message when sign-in is throttled", async () => {
    stubApi({
      "GET /api/v1/auth/me": NO_SESSION,
      "POST /api/v1/auth/login": {
        status: 429,
        body: {
          error: {
            code: "too_many_attempts",
            message: "Too many failed sign-in attempts. Try again in 15 minutes.",
            details: {},
          },
        },
      },
    });
    renderWithClient(<LoginForm />);

    await fillAndSubmit("admin@acme.test", "wrong-password");

    expect(
      await screen.findByText("Too many failed sign-in attempts. Try again in 15 minutes."),
    ).toBeTruthy();
  });

  it("validates empty fields without calling the backend", async () => {
    const fetchMock = stubApi({ "GET /api/v1/auth/me": NO_SESSION });
    renderWithClient(<LoginForm />);

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter your email address.")).toBeTruthy();
    expect(screen.getByText("Enter your password.")).toBeTruthy();
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe("true");
    expect(fetchMock.mock.calls.every(([request]) => request.method === "GET")).toBe(true);
  });

  it("leaves the login page when a session already exists", async () => {
    stubApi({ "GET /api/v1/auth/me": { status: 200, body: ME } });
    renderWithClient(<LoginForm />);

    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/dashboard"));
  });
});

describe("LoginForm review fixes", () => {
  it("ignores a dot-segment ?next= that normalizes to another host", async () => {
    searchParams = new URLSearchParams({ next: "/..//evil.example" });
    stubApi({ "GET /api/v1/auth/me": { status: 200, body: ME } });
    renderWithClient(<LoginForm />);

    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/dashboard"));
    expect(routerReplace).not.toHaveBeenCalledWith("//evil.example");
  });

  it("stops redirecting when its last redirect bounced straight back (no loop)", async () => {
    markLoginRedirect();
    stubApi({ "GET /api/v1/auth/me": { status: 200, body: ME } });
    renderWithClient(<LoginForm />);

    expect(await screen.findByText(/can't see the session cookie/)).toBeTruthy();
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("shows a message for a 422 that names no field on the form", async () => {
    stubApi({
      "GET /api/v1/auth/me": NO_SESSION,
      "POST /api/v1/auth/login": {
        status: 422,
        body: {
          error: {
            code: "validation_error",
            message: "The request is invalid.",
            details: { errors: [{ loc: ["body"], msg: "Field required", type: "missing" }] },
          },
        },
      },
    });
    renderWithClient(<LoginForm />);

    await fillAndSubmit("admin@example.com", "x");

    expect(await screen.findByText("Check your email and password.")).toBeTruthy();
  });

  it("puts a 422 field error next to its field", async () => {
    stubApi({
      "GET /api/v1/auth/me": NO_SESSION,
      "POST /api/v1/auth/login": {
        status: 422,
        body: {
          error: {
            code: "validation_error",
            message: "The request is invalid.",
            details: { errors: [{ loc: ["body", "email"], msg: "Too long", type: "too_long" }] },
          },
        },
      },
    });
    renderWithClient(<LoginForm />);

    await fillAndSubmit("admin@example.com", "x");

    expect(await screen.findByText("Too long")).toBeTruthy();
    expect(screen.queryByText("Check your email and password.")).toBeNull();
  });

  it("accepts an address without a dotted domain and lets the backend decide", async () => {
    stubApi({
      "GET /api/v1/auth/me": NO_SESSION,
      "POST /api/v1/auth/login": { status: 200, body: ME },
    });
    renderWithClient(<LoginForm />);

    await fillAndSubmit("admin@localhost", "releaseguard-dev");

    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/dashboard"));
  });
});

describe("AuthGuard", () => {
  it("keeps the page when a background re-check fails after the session was confirmed", async () => {
    window.history.replaceState({}, "", "/dashboard");
    const client = makeQueryClient();
    client.setQueryDefaults(meQueryKey, { retry: false });
    client.setQueryData(meQueryKey, ME);
    stubApi({
      "GET /api/v1/auth/me": {
        status: 503,
        body: { error: { code: "unavailable", message: "Restarting.", details: {} } },
      },
    });
    render(
      <QueryClientProvider client={client}>
        <AuthGuard>
          <p>secret page</p>
        </AuthGuard>
      </QueryClientProvider>,
    );

    await act(() => client.refetchQueries({ queryKey: meQueryKey }));

    expect(client.getQueryState(meQueryKey)?.status).toBe("error");
    expect(screen.getByText("secret page")).toBeTruthy();
  });

  it("shows a loading state, then the page once the session is confirmed", async () => {
    window.history.replaceState({}, "", "/dashboard");
    stubApi({ "GET /api/v1/auth/me": { status: 200, body: ME } });
    renderWithClient(
      <AuthGuard>
        <p>secret page</p>
      </AuthGuard>,
    );

    expect(screen.getByRole("status").textContent).toContain("Checking your session");
    expect(await screen.findByText("secret page")).toBeTruthy();
  });

  it("never renders the page without a valid session", async () => {
    window.history.replaceState({}, "", "/dashboard");
    const replace = vi.fn();
    vi.stubGlobal("location", { ...window.location, pathname: "/dashboard", search: "", replace });
    stubApi({ "GET /api/v1/auth/me": NO_SESSION });
    renderWithClient(
      <AuthGuard>
        <p>secret page</p>
      </AuthGuard>,
    );

    expect(await screen.findByText("Redirecting to sign in…")).toBeTruthy();
    expect(screen.queryByText("secret page")).toBeNull();
  });
});

describe("initials", () => {
  it.each([
    ["Ada Lovelace", "AL"],
    ["ada", "A"],
    ["  Grace  Brewster Hopper ", "GH"],
    ["", "?"],
  ])("%s → %s", (name, expected) => {
    expect(initials(name)).toBe(expected);
  });
});
