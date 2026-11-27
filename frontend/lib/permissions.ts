import type { Role } from "@/services/auth";

/**
 * The role matrix from `backend/app/core/permissions.py` (guide §3.1), mirrored only to hide
 * controls a role can't use. **Not authorization:** the backend checks every request and
 * answers 403, which the UI shows as the permission-denied state.
 */
export type Capability =
  | "view"
  | "manage_workspace"
  | "manage_github_integration"
  | "manage_applications"
  | "configure_environments"
  | "register_releases"
  | "request_deployments"
  | "decide_approvals"
  | "initiate_rollbacks"
  | "request_ai_analysis";

const EVERYONE: readonly Capability[] = ["view", "request_ai_analysis"];

export const ROLE_CAPABILITIES: Readonly<Record<Role, ReadonlySet<Capability>>> = {
  admin: new Set<Capability>([
    ...EVERYONE,
    "manage_workspace",
    "manage_github_integration",
    "manage_applications",
    "configure_environments",
    "register_releases",
    "request_deployments",
    "decide_approvals",
    "initiate_rollbacks",
  ]),
  developer: new Set<Capability>([
    ...EVERYONE,
    "manage_applications",
    "register_releases",
    "request_deployments",
    "initiate_rollbacks",
  ]),
  reviewer: new Set<Capability>([...EVERYONE, "decide_approvals"]),
  viewer: new Set<Capability>(EVERYONE),
};

/** Whether `role` may use `capability`; `false` while the role isn't known yet. */
export function can(role: Role | undefined, capability: Capability): boolean {
  return role !== undefined && ROLE_CAPABILITIES[role].has(capability);
}
