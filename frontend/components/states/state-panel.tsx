import type { LucideIcon } from "lucide-react";
import { useId } from "react";

import { cn } from "cn";

type StatePanelProps = {
  icon: LucideIcon;
  title: string;
  description?: React.ReactNode;
  /** A button or link: the one next step (retry, create, go back). */
  action?: React.ReactNode;
  /** `alert` for errors (announced at once), otherwise a plain region. */
  role?: "alert";
  tone?: "muted" | "destructive";
  /** `h1` when the state is the whole page (a 404), `h2` inside a page. */
  headingLevel?: "h1" | "h2";
  className?: string;
};

/** Shared layout of the empty, error and permission-denied states: icon, title, text, action. */
export function StatePanel({
  icon: Icon,
  title,
  description,
  action,
  role,
  tone = "muted",
  headingLevel: Heading = "h2",
  className,
}: StatePanelProps) {
  const titleId = useId();
  return (
    <section
      role={role}
      aria-labelledby={titleId}
      className={cn(
        "flex flex-1 flex-col items-center justify-center gap-3 px-4 py-16 text-center",
        className,
      )}
    >
      <Icon
        className={cn(
          "size-10",
          tone === "destructive" ? "text-destructive" : "text-muted-foreground",
        )}
        aria-hidden="true"
      />
      <Heading id={titleId} className="text-xl font-semibold tracking-tight">
        {title}
      </Heading>
      {description ? (
        <div className="max-w-md text-sm text-muted-foreground">{description}</div>
      ) : null}
      {action ? <div className="mt-1 flex flex-wrap justify-center gap-2">{action}</div> : null}
    </section>
  );
}
