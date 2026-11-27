import { ApiError } from "@/services/api";

/**
 * A 422 `validation_error` → `[field, message]` pairs for the fields a form shows. The backend
 * sends `details.errors[] = {loc, msg, type}` with `loc` like `["body", "policy", "min_approvals"]`;
 * the field name is `loc` without its leading `"body"`, joined with `.` (`policy.min_approvals`),
 * the same path React Hook Form uses. Errors for fields not in `fields` are dropped.
 */
export function fieldErrors<F extends string>(
  error: unknown,
  fields: ReadonlySet<F>,
): Array<[F, string]> {
  if (!(error instanceof ApiError) || error.status !== 422) return [];
  const errors = error.details.errors;
  if (!Array.isArray(errors)) return [];
  return errors.flatMap((item: unknown): Array<[F, string]> => {
    if (typeof item !== "object" || item === null) return [];
    const { loc, msg } = item as { loc?: unknown; msg?: unknown };
    if (!Array.isArray(loc) || typeof msg !== "string") return [];
    const path = (loc[0] === "body" ? loc.slice(1) : loc).map(String).join(".");
    return (fields as ReadonlySet<string>).has(path) ? [[path as F, msg]] : [];
  });
}
