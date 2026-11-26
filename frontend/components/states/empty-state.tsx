import { Inbox, type LucideIcon } from "lucide-react";

import { StatePanel } from "@/components/states/state-panel";

type EmptyStateProps = {
  title: string;
  description?: React.ReactNode;
  /** Usually the action that fills the list ("Create application"). */
  action?: React.ReactNode;
  icon?: LucideIcon;
  headingLevel?: "h1" | "h2";
};

/** Nothing to show yet (an empty list, no search results, a missing page). */
export function EmptyState({ icon = Inbox, ...props }: EmptyStateProps) {
  return <StatePanel icon={icon} {...props} />;
}
