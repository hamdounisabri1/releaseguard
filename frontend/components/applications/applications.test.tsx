// @vitest-environment jsdom
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDetails } from "@/components/applications/application-details";
import { ApplicationsList, matchesSearch } from "@/components/applications/applications-list";
import type { Application, Environment } from "@/services/applications";
import { errorReply, meReply, renderWithClient, requestsTo, stubApi } from "@/test-utils/api-stub";

vi.mock("@/lib/env", () => ({ apiBaseUrl: "http://api.test/api/v1" }));

const routerPush = vi.fn();
let params: Record<string, string> = {};
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, replace: vi.fn() }),
  useParams: () => params,
}));

afterEach(() => {
  cleanup();
  routerPush.mockReset();
  params = {};
});

function application(overrides: Partial<Application> = {}): Application {
  return {
    id: "a1",
    name: "TaskFlow",
    description: "Sample task app",
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
    ...overrides,
  };
}

function environment(overrides: Partial<Environment> = {}): Environment {
  return {
    id: "e-prod",
    application_id: "a1",
    environment_type: "production",
    health_url: null,
    expected_status: 200,
    check_interval_seconds: 60,
    timeout_ms: 5000,
    failure_threshold: 3,
    verify_successes: 3,
    verify_timeout_seconds: 300,
    health_status: "unknown",
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
    ...overrides,
  };
}

function page(items: Application[]) {
  return { status: 200, body: { items, page: 1, page_size: 100, total: items.length } };
}

const APPS = [
  application(),
  application({
    id: "a2",
    name: "Billing",
    description: "",
    repository_owner: "acme",
    repository_name: "billing-api",
  }),
];

describe("matchesSearch", () => {
  it("matches name, description and owner/name, ignoring case and spaces", () => {
    expect(matchesSearch(APPS[0], "  TASK ")).toBe(true);
    expect(matchesSearch(APPS[0], "sample")).toBe(true);
    expect(matchesSearch(APPS[1], "acme/billing")).toBe(true);
    expect(matchesSearch(APPS[1], "taskflow")).toBe(false);
    expect(matchesSearch(APPS[1], "")).toBe(true);
  });
});

describe("ApplicationsList", () => {
  it("lists applications and filters them by the search", async () => {
    stubApi({ "GET /api/v1/auth/me": meReply("admin"), "GET /api/v1/applications": page(APPS) });
    renderWithClient(<ApplicationsList />);

    const link = await screen.findByRole("link", { name: "TaskFlow" });
    expect(link.getAttribute("href")).toBe("/applications/a1");
    expect(screen.getByRole("link", { name: "Billing" })).toBeTruthy();

    await userEvent.setup().type(screen.getByLabelText("Search applications"), "billing");
    expect(screen.queryByRole("link", { name: "TaskFlow" })).toBeNull();
    expect(screen.getByRole("link", { name: "Billing" })).toBeTruthy();
  });

  it("says so when the search matches nothing", async () => {
    stubApi({ "GET /api/v1/auth/me": meReply("admin"), "GET /api/v1/applications": page(APPS) });
    renderWithClient(<ApplicationsList />);
    await screen.findByRole("link", { name: "TaskFlow" });

    await userEvent.setup().type(screen.getByLabelText("Search applications"), "zzz");
    expect(screen.getByText("No matching applications")).toBeTruthy();
  });

  it("shows the empty state when there are no applications", async () => {
    stubApi({ "GET /api/v1/auth/me": meReply("admin"), "GET /api/v1/applications": page([]) });
    renderWithClient(<ApplicationsList />);
    expect(await screen.findByText("No applications yet")).toBeTruthy();
  });

  it("shows the loading state, then the error state with a retry on a 5xx", async () => {
    stubApi({
      "GET /api/v1/auth/me": meReply("admin"),
      "GET /api/v1/applications": errorReply(503, "unavailable", "Down."),
    });
    renderWithClient(<ApplicationsList />);
    expect(screen.getByText("Loading applications…")).toBeTruthy();
    expect(
      await screen.findByRole("button", { name: "Try again" }, { timeout: 5000 }),
    ).toBeTruthy();
  });

  it("asks for archived applications when 'Show archived' is on", async () => {
    const fetchMock = stubApi({
      "GET /api/v1/auth/me": meReply("admin"),
      "GET /api/v1/applications": (request) =>
        new URL(request.url).searchParams.get("include_archived") === "true"
          ? page([...APPS, application({ id: "a3", name: "Old", status: "archived" })])
          : page(APPS),
    });
    renderWithClient(<ApplicationsList />);
    await screen.findByRole("link", { name: "TaskFlow" });

    await userEvent.setup().click(screen.getByRole("switch", { name: "Show archived" }));
    expect(await screen.findByRole("link", { name: "Old" })).toBeTruthy();
    expect(screen.getByText("Archived")).toBeTruthy();
    const urls = requestsTo(fetchMock, "GET /api/v1/applications").map((r) => r.url);
    expect(urls.some((url) => url.includes("include_archived=true"))).toBe(true);
  });

  it.each(["viewer", "reviewer"] as const)(
    "shows a %s no create or archive controls",
    async (role) => {
      stubApi({ "GET /api/v1/auth/me": meReply(role), "GET /api/v1/applications": page(APPS) });
      renderWithClient(<ApplicationsList />);
      await screen.findByRole("link", { name: "TaskFlow" });
      expect(screen.queryByRole("button", { name: /new application/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /archive/i })).toBeNull();
    },
  );

  it("creates an application and opens it", async () => {
    let created = false;
    const fetchMock = stubApi({
      "GET /api/v1/auth/me": meReply("developer"),
      "GET /api/v1/applications": () => page(created ? [...APPS, application({ id: "a9" })] : APPS),
      "POST /api/v1/applications": () => {
        created = true;
        return { status: 201, body: application({ id: "a9", name: "Shop" }) };
      },
    });
    const user = userEvent.setup();
    renderWithClient(<ApplicationsList />);
    await user.click(await screen.findByRole("button", { name: "New application" }));

    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Shop");
    await user.type(within(dialog).getByLabelText("Repository owner"), "acme");
    await user.type(within(dialog).getByLabelText("Repository name"), "shop");
    await user.click(within(dialog).getByRole("button", { name: "Create application" }));

    await waitFor(() => expect(routerPush).toHaveBeenCalledWith("/applications/a9"));
    const [request] = requestsTo(fetchMock, "POST /api/v1/applications");
    expect(await request.json()).toMatchObject({
      name: "Shop",
      repository_owner: "acme",
      repository_name: "shop",
      default_branch: "main",
      deploy_workflow_path: ".github/workflows/deploy.yml",
    });
    // The list was refetched after the create.
    expect(requestsTo(fetchMock, "GET /api/v1/applications").length).toBeGreaterThan(1);
  });

  it("checks the form before sending it", async () => {
    const fetchMock = stubApi({
      "GET /api/v1/auth/me": meReply("admin"),
      "GET /api/v1/applications": page(APPS),
    });
    const user = userEvent.setup();
    renderWithClient(<ApplicationsList />);
    await user.click(await screen.findByRole("button", { name: "New application" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Repository owner"), "-bad");
    await user.click(within(dialog).getByRole("button", { name: "Create application" }));

    expect(await within(dialog).findByText("Enter a name.")).toBeTruthy();
    expect(within(dialog).getByText("Enter a GitHub user or organization name.")).toBeTruthy();
    expect(requestsTo(fetchMock, "POST /api/v1/applications")).toHaveLength(0);
  });

  it("shows a taken repository (409) and server 422s next to their fields", async () => {
    let attempt = 0;
    stubApi({
      "GET /api/v1/auth/me": meReply("admin"),
      "GET /api/v1/applications": page(APPS),
      "POST /api/v1/applications": () =>
        ++attempt === 1
          ? errorReply(
              409,
              "repository_already_registered",
              "Another application in this workspace already uses this repository.",
            )
          : errorReply(422, "validation_error", "The request is invalid.", {
              errors: [{ loc: ["body", "name"], msg: "Name is reserved", type: "value_error" }],
            }),
    });
    const user = userEvent.setup();
    renderWithClient(<ApplicationsList />);
    await user.click(await screen.findByRole("button", { name: "New application" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Again");
    await user.type(within(dialog).getByLabelText("Repository owner"), "acme");
    await user.type(within(dialog).getByLabelText("Repository name"), "taskflow");
    const submit = within(dialog).getByRole("button", { name: "Create application" });

    await user.click(submit);
    const repoName = within(dialog).getByLabelText("Repository name");
    await waitFor(() => expect(repoName.getAttribute("aria-invalid")).toBe("true"));
    expect(within(dialog).getByText(/already uses this repository/)).toBeTruthy();

    await user.click(submit);
    expect(await within(dialog).findByText("Name is reserved")).toBeTruthy();
    expect(within(dialog).getByLabelText("Name").getAttribute("aria-invalid")).toBe("true");
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("archives after confirmation and refreshes the list", async () => {
    let archived = false;
    const fetchMock = stubApi({
      "GET /api/v1/auth/me": meReply("admin"),
      "GET /api/v1/applications": () => page(archived ? [APPS[1]] : APPS),
      "POST /api/v1/applications/a1/archive": () => {
        archived = true;
        return { status: 200, body: application({ status: "archived" }) };
      },
    });
    const user = userEvent.setup();
    renderWithClient(<ApplicationsList />);
    await screen.findByRole("link", { name: "TaskFlow" });
    await user.click(screen.getByRole("button", { name: "Archive TaskFlow" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(requestsTo(fetchMock, "POST /api/v1/applications/a1/archive")).toHaveLength(0);

    await user.click(within(dialog).getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(screen.queryByRole("link", { name: "TaskFlow" })).toBeNull());
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("keeps the dialog open with the reason when archiving is refused (403)", async () => {
    stubApi({
      "GET /api/v1/auth/me": meReply("developer"),
      "GET /api/v1/applications": page(APPS),
      "POST /api/v1/applications/a1/archive": errorReply(403, "forbidden"),
    });
    const user = userEvent.setup();
    renderWithClient(<ApplicationsList />);
    await screen.findByRole("link", { name: "TaskFlow" });
    await user.click(screen.getByRole("button", { name: "Archive TaskFlow" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Archive" }));

    const alert = await within(dialog).findByRole("alert");
    expect(alert.textContent).toContain("doesn't allow archiving applications");
  });
});

describe("ApplicationDetails", () => {
  it("shows the application and its environments in promotion order", async () => {
    params = { applicationId: "a1" };
    stubApi({
      "GET /api/v1/auth/me": meReply("viewer"),
      "GET /api/v1/applications/a1": { status: 200, body: application() },
      "GET /api/v1/applications/a1/environments": {
        status: 200,
        body: [
          environment(),
          environment({ id: "e-dev", environment_type: "development", health_status: "healthy" }),
          environment({ id: "e-stg", environment_type: "staging", health_status: "unhealthy" }),
        ],
      },
    });
    renderWithClient(<ApplicationDetails />);

    expect(await screen.findByRole("heading", { level: 1, name: /TaskFlow/ })).toBeTruthy();
    const headings = await screen.findAllByRole("heading", { level: 3 });
    expect(headings.map((h) => h.textContent)).toEqual([
      "DevelopmentHealth: Healthy",
      "StagingHealth: Unhealthy",
      "ProductionHealth: Unknown",
    ]);
    // A Viewer gets no archive control.
    expect(screen.queryByRole("button", { name: /archive/i })).toBeNull();
  });

  it("shows the not-found state for an unknown or foreign application (404)", async () => {
    params = { applicationId: "nope" };
    stubApi({
      "GET /api/v1/auth/me": meReply("admin"),
      "GET /api/v1/applications/nope": errorReply(404, "not_found", "Not found."),
    });
    renderWithClient(<ApplicationDetails />);
    expect(await screen.findByRole("link", { name: /back to dashboard/i })).toBeTruthy();
    expect(screen.queryByRole("tablist")).toBeNull();
  });
});
