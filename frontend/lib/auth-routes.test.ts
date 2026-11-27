import { describe, expect, it } from "vitest";

import { DEFAULT_AFTER_LOGIN, safeNextPath } from "@/lib/auth-routes";

describe("safeNextPath", () => {
  it.each(["/dashboard", "/applications/abc?tab=environments", "/approvals#pending"])(
    "keeps the same-site path %s",
    (path) => {
      expect(safeNextPath(path)).toBe(path);
    },
  );

  it.each([
    null,
    undefined,
    "",
    "dashboard",
    "//evil.example/phish",
    "/\\evil.example",
    "https://evil.example/",
    "javascript:alert(1)",
    "/login",
    "/login?next=/dashboard",
    "/login/",
    // Dot segments that normalize to a protocol-relative URL (release-safety review, SCRUM-28).
    "/..//evil.example",
    "/a/..//evil.example",
    "/%2e%2e//evil.example",
    "/./../\\evil.example",
    "/../login",
  ])("falls back to the dashboard for %s", (raw) => {
    expect(safeNextPath(raw)).toBe(DEFAULT_AFTER_LOGIN);
  });
});
