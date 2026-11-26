import { ShieldX } from "lucide-react";
import Link from "next/link";

import { StatePanel } from "@/components/states/state-panel";
import { Button } from "@/components/ui/button";

type PermissionDeniedProps = {
  /** What the user tried to reach or do, for the message ("change environment settings"). */
  what?: string;
};

/**
 * The backend refused the request for this user's role (403). The backend is the authority;
 * this only explains it. A resource in another workspace is a 404, never this state.
 */
export function PermissionDenied({ what = "view this page" }: PermissionDeniedProps) {
  return (
    <StatePanel
      icon={ShieldX}
      title="You don't have access"
      description={`Your role in this workspace doesn't allow you to ${what}. Ask a workspace admin if you need access.`}
      action={
        <Button asChild variant="outline">
          <Link href="/dashboard">Back to dashboard</Link>
        </Button>
      }
    />
  );
}
