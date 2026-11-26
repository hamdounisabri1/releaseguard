// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiErrorState } from "@/components/states/api-error-state";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";
import { ApiError } from "@/services/api";

afterEach(cleanup);

describe("ErrorState", () => {
  it("shows the message as an alert and retries on click", async () => {
    const onRetry = vi.fn();
    render(<ErrorState message="The database is unreachable." onRetry={onRetry} />);

    const alert = screen.getByRole("alert", { name: "Something went wrong" });
    expect(alert.textContent).toContain("The database is unreachable.");

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("has no retry button without onRetry", () => {
    render(<ErrorState message="Nope." />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ApiErrorState", () => {
  it("shows the API error message with a retry for a 5xx", async () => {
    const onRetry = vi.fn();
    render(
      <ApiErrorState
        error={new ApiError(503, "unavailable", "ReleaseGuard is restarting.")}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByRole("alert").textContent).toContain("ReleaseGuard is restarting.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows a 4xx message without a retry", () => {
    render(
      <ApiErrorState
        error={new ApiError(409, "conflict", "Already archived.")}
        onRetry={() => {}}
      />,
    );

    expect(screen.getByRole("alert").textContent).toContain("Already archived.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("renders permission denied for a 403", () => {
    render(<ApiErrorState error={new ApiError(403, "forbidden", "Forbidden")} />);

    expect(screen.getByRole("heading", { name: "You don't have access" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to dashboard" }).getAttribute("href")).toBe(
      "/dashboard",
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders not found for a 404", () => {
    render(<ApiErrorState error={new ApiError(404, "not_found", "Application not found.")} />);

    expect(screen.getByRole("heading", { name: "Not found" })).toBeTruthy();
    expect(screen.getByText("Application not found.")).toBeTruthy();
  });

  it("shows only a loading status for a 401 (the client is redirecting)", () => {
    render(<ApiErrorState error={new ApiError(401, "session_expired", "Session expired")} />);

    expect(screen.getByRole("status").textContent).toContain("Redirecting to sign in");
  });

  it("hides a non-API error's text but shows its digest", () => {
    const error = Object.assign(new Error("connection string leaked here"), { digest: "abc123" });
    render(<ApiErrorState error={error} onRetry={() => {}} />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).not.toContain("leaked");
    expect(alert.textContent).toContain("abc123");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

describe("EmptyState and LoadingState", () => {
  it("renders the empty state's title, text and action", () => {
    render(
      <EmptyState
        title="No applications yet"
        description="Create one to get started."
        action={<button type="button">Create application</button>}
      />,
    );

    expect(screen.getByRole("region", { name: "No applications yet" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create application" })).toBeTruthy();
  });

  it("announces loading and hides the skeleton from screen readers", () => {
    render(<LoadingState label="Loading applications…" />);

    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-busy")).toBe("true");
    expect(status.textContent).toBe("Loading applications…");
  });
});
