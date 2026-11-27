import { Badge } from "@/components/ui/badge";
import type { Application } from "@/services/applications";

/** Active or Archived. An archived application keeps its history but takes no new work. */
export function ApplicationStatusBadge({ status }: { status: Application["status"] }) {
  return status === "archived" ? (
    <Badge variant="secondary">Archived</Badge>
  ) : (
    <Badge variant="outline">Active</Badge>
  );
}
