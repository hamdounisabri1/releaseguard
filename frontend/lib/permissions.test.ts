import { describe, expect, it } from "vitest";

import { can, ROLE_CAPABILITIES } from "@/lib/permissions";

// Guide §3.1, as in backend/app/core/permissions.py. UX only: the backend enforces it.
describe("can", () => {
  it("lets only Admins configure environments", () => {
    expect(can("admin", "configure_environments")).toBe(true);
    for (const role of ["developer", "reviewer", "viewer"] as const) {
      expect(can(role, "configure_environments")).toBe(false);
    }
  });

  it("lets Admins and Developers manage applications", () => {
    expect(can("admin", "manage_applications")).toBe(true);
    expect(can("developer", "manage_applications")).toBe(true);
    expect(can("reviewer", "manage_applications")).toBe(false);
    expect(can("viewer", "manage_applications")).toBe(false);
  });

  it("gives Viewers read access only", () => {
    expect([...ROLE_CAPABILITIES.viewer].sort()).toEqual(["request_ai_analysis", "view"]);
  });

  it("gives Reviewers approvals on top of read access", () => {
    expect([...ROLE_CAPABILITIES.reviewer].sort()).toEqual([
      "decide_approvals",
      "request_ai_analysis",
      "view",
    ]);
  });

  it("denies everything while the role is unknown", () => {
    expect(can(undefined, "view")).toBe(false);
  });
});
