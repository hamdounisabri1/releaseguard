// @vitest-environment jsdom
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDetails } from "@/components/applications/application-details";
import { EnvironmentSettings } from "@/components/environments/environment-settings";
import { changedSettings } from "@/components/environments/environment-settings-form";
import type { Environment } from "@/services/applications";
import { errorReply, meReply, renderWithClient, requestsTo, stubApi } from "@/test-utils/api-stub";

vi.mock("@/lib/env", () => ({ apiBaseUrl: "http://api.test/api/v1" }));

let params: Record<string, string> = {};
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => params,
}));

afterEach(() => {
  cleanup();
  params = {};
});

const ENV: Environment = {
  id: "e-prod",
  application_id: "a1",
  environment_type: "production",
  health_url: "https://taskflow.example/healthz",
  expected_status: 200,
  check_interval_seconds: 60,
  timeout_ms: 5000,
  failure_threshold: 3,
  verify_successes: 3,
  verify_timeout_seconds: 300,
  health_status: "healthy",
  consecutive_failures: 0,
  current_deployment_id: null,
  last_checked_at: null,
  next_check_at: null,
  created_at: "2026-11-27T09:00:00Z",
  policy: {
    auto_deploy_on_release: false,
    requires_approval: true,
    min_approvals: 1,
    approval_ttl_hours: 24,
    require_comment: false,
    promote_from_environment_id: null,
    rollback_requires_approval: false,
  },
};

const APP = {
  id: "a1",
  name: "TaskFlow",
  description: "",
  repository_owner: "acme",
  repository_name: "taskflow",
  repository_id: 42,
  default_branch: "main",
  ci_workflow_path: ".github/workflows/ci.yml",
  deploy_workflow_path: ".github/workflows/deploy.yml",
  status: "active",
  archived_at: null,
  created_at: "2026-11-27T09:00:00Z",
  updated_at: "2026-11-27T09:00:00Z",
};

function routes(role: "admin" | "developer" | "viewer", overrides = {}) {
  return {
    "GET /api/v1/auth/me": meReply(role),
    "GET /api/v1/applications/a1": { status: 200, body: APP },
    "GET /api/v1/environments/e-prod": { status: 200, body: ENV },
    ...overrides,
  };
}

async function replaceValue(label: string, value: string) {
  const user = userEvent.setup();
  const input = screen.getByLabelText(label);
  await user.clear(input);
  if (value) await user.type(input, value);
  return user;
}

describe("changedSettings", () => {
  it("keeps only the fields that differ from the saved environment", () => {
    const values = {
      expected_status: 200,
      check_interval_seconds: 30,
      timeout_ms: 5000,
      failure_threshold: 3,
      verify_successes: 5,
      verify_timeout_seconds: 300,
    };
    expect(changedSettings(ENV, values)).toEqual({
      check_interval_seconds: 30,
      verify_successes: 5,
    });
  });
});

describe("EnvironmentSettings", () => {
  it("loads the saved values, saves only the changes and shows the saved values", async () => {
    params = { applicationId: "a1", environmentId: "e-prod" };
    let current = ENV;
    const fetchMock = stubApi(
      routes("admin", {
        "GET /api/v1/environments/e-prod": () => ({ status: 200, body: current }),
        "PATCH /api/v1/environments/e-prod": async (request: Request) => {
          current = { ...current, ...(await request.json()) };
          return { status: 200, body: current };
        },
      }),
    );
    renderWithClient(<EnvironmentSettings />);

    const interval = (await screen.findByLabelText("Check interval (seconds)")) as HTMLInputElement;
    expect(interval.value).toBe("60");
    const healthUrl = screen.getByLabelText("Health URL") as HTMLInputElement;
    expect(healthUrl.value).toBe("https://taskflow.example/healthz");
    expect(healthUrl.readOnly).toBe(true);

    const user = await replaceValue("Check interval (seconds)", "30");
    await replaceValue("Healthy checks required", "5");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    expect(await screen.findByText("Settings saved.")).toBeTruthy();
    const [patch] = requestsTo(fetchMock, "PATCH /api/v1/environments/e-prod");
    expect(await patch.json()).toEqual({ check_interval_seconds: 30, verify_successes: 5 });
    expect(interval.value).toBe("30");
    expect((screen.getByLabelText("Healthy checks required") as HTMLInputElement).value).toBe("5");
  });

  it("reloads the saved values on a fresh visit", async () => {
    params = { applicationId: "a1", environmentId: "e-prod" };
    stubApi(
      routes("admin", {
        "GET /api/v1/environments/e-prod": {
          status: 200,
          body: { ...ENV, check_interval_seconds: 30, timeout_ms: 2500 },
        },
      }),
    );
    renderWithClient(<EnvironmentSettings />);
    const interval = (await screen.findByLabelText("Check interval (seconds)")) as HTMLInputElement;
    expect(interval.value).toBe("30");
    expect((screen.getByLabelText("Timeout (ms)") as HTMLInputElement).value).toBe("2500");
  });

  it("checks the bounds before sending", async () => {
    params = { applicationId: "a1", environmentId: "e-prod" };
    const fetchMock = stubApi(routes("admin"));
    renderWithClient(<EnvironmentSettings />);
    await screen.findByLabelText("Timeout (ms)");

    const user = await replaceValue("Timeout (ms)", "99");
    await replaceValue("Failure threshold", "");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    expect(await screen.findByText("Use 100 or more.")).toBeTruthy();
    expect(screen.getByText("Enter a number.")).toBeTruthy();
    expect(requestsTo(fetchMock, "PATCH /api/v1/environments/e-prod")).toHaveLength(0);
  });

  it("shows server validation errors (422) next to the field", async () => {
    params = { applicationId: "a1", environmentId: "e-prod" };
    stubApi(
      routes("admin", {
        "PATCH /api/v1/environments/e-prod": errorReply(422, "validation_error", "Invalid.", {
          errors: [
            {
              loc: ["body", "timeout_ms"],
              msg: "Input should be less than or equal to 60000",
              type: "less_than_equal",
            },
          ],
        }),
      }),
    );
    renderWithClient(<EnvironmentSettings />);
    await screen.findByLabelText("Timeout (ms)");

    const user = await replaceValue("Timeout (ms)", "6000");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    expect(await screen.findByText("Input should be less than or equal to 60000")).toBeTruthy();
    const timeout = screen.getByLabelText("Timeout (ms)");
    expect(timeout.getAttribute("aria-invalid")).toBe("true");
    expect(timeout.getAttribute("aria-describedby")).toContain("env-timeout-error");
    expect(screen.queryByText("Settings saved.")).toBeNull();
  });

  it.each(["developer", "viewer"] as const)(
    "gives a %s the permission-denied state and loads nothing",
    async (role) => {
      params = { applicationId: "a1", environmentId: "e-prod" };
      const fetchMock = stubApi(routes(role));
      renderWithClient(<EnvironmentSettings />);

      expect(await screen.findByText("You don't have access")).toBeTruthy();
      expect(screen.queryByRole("button", { name: "Save settings" })).toBeNull();
      expect(requestsTo(fetchMock, "GET /api/v1/environments/e-prod")).toHaveLength(0);
    },
  );

  it("switches to the permission-denied state when the backend refuses the save (403)", async () => {
    params = { applicationId: "a1", environmentId: "e-prod" };
    stubApi(routes("admin", { "PATCH /api/v1/environments/e-prod": errorReply(403, "forbidden") }));
    renderWithClient(<EnvironmentSettings />);
    await screen.findByLabelText("Timeout (ms)");

    const user = await replaceValue("Timeout (ms)", "2000");
    await user.click(screen.getByRole("button", { name: "Save settings" }));
    expect(await screen.findByText("You don't have access")).toBeTruthy();
  });

  it("treats an environment of another application as not found", async () => {
    params = { applicationId: "a2", environmentId: "e-prod" };
    stubApi(
      routes("admin", {
        "GET /api/v1/applications/a2": { status: 200, body: { ...APP, id: "a2" } },
      }),
    );
    renderWithClient(<EnvironmentSettings />);
    expect(await screen.findByText("Not found")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save settings" })).toBeNull();
  });
});

describe("Configure link", () => {
  it.each([
    ["admin", 1],
    ["developer", 0],
  ] as const)("is shown to %s: %i", async (role, count) => {
    params = { applicationId: "a1" };
    stubApi(
      routes(role, {
        "GET /api/v1/applications/a1/environments": { status: 200, body: [ENV] },
      }),
    );
    renderWithClient(<ApplicationDetails />);
    await screen.findByRole("heading", { level: 3 });
    await waitFor(() =>
      expect(screen.queryAllByRole("link", { name: "Configure Production" })).toHaveLength(count),
    );
  });
});
