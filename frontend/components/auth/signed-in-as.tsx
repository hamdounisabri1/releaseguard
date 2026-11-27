"use client";

import { useQuery } from "@tanstack/react-query";

import { meQueryOptions, roleLabel } from "@/services/auth";

/** "Signed in as … · workspace · role", from the `/auth/me` query `AuthGuard` already loaded. */
export function SignedInAs() {
  const { data: me } = useQuery(meQueryOptions);
  if (!me) return null;
  return (
    <p className="text-sm text-muted-foreground">
      Signed in as <span className="font-medium text-foreground">{me.user.display_name}</span> in{" "}
      <span className="font-medium text-foreground">{me.workspace.name}</span> ·{" "}
      {roleLabel(me.role)}
    </p>
  );
}
