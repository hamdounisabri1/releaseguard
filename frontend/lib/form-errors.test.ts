import { describe, expect, it } from "vitest";

import { fieldErrors } from "@/lib/form-errors";
import { ApiError } from "@/services/api";

const FIELDS = new Set(["timeout_ms", "policy.min_approvals"] as const);

function validationError(errors: unknown): ApiError {
  return new ApiError(422, "validation_error", "The request is invalid.", { errors });
}

describe("fieldErrors", () => {
  it("maps body locations to field paths, nested ones joined with a dot", () => {
    const error = validationError([
      { loc: ["body", "timeout_ms"], msg: "too big", type: "less_than_equal" },
      { loc: ["body", "policy", "min_approvals"], msg: "too small", type: "greater_than_equal" },
    ]);
    expect(fieldErrors(error, FIELDS)).toEqual([
      ["timeout_ms", "too big"],
      ["policy.min_approvals", "too small"],
    ]);
  });

  it("drops fields the form doesn't show and malformed items", () => {
    const error = validationError([
      { loc: ["body", "health_url"], msg: "extra", type: "extra_forbidden" },
      { loc: "body.timeout_ms", msg: "not a list" },
      { loc: ["body", "timeout_ms"], msg: 42 },
      null,
    ]);
    expect(fieldErrors(error, FIELDS)).toEqual([]);
  });

  it("ignores anything but a 422 with an errors list", () => {
    expect(fieldErrors(new ApiError(409, "conflict", "x"), FIELDS)).toEqual([]);
    expect(fieldErrors(validationError("nope"), FIELDS)).toEqual([]);
    expect(fieldErrors(new Error("network"), FIELDS)).toEqual([]);
  });
});
