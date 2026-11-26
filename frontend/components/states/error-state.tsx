import { CircleAlert, RotateCw } from "lucide-react";

import { StatePanel } from "@/components/states/state-panel";
import { Button } from "@/components/ui/button";

type ErrorStateProps = {
  title?: string;
  /** What went wrong, in plain words (an `ApiError` message is written for people). */
  message: string;
  /** Shows a "Try again" button; omit it when a retry can't help. */
  onRetry?: () => void;
  /** A support reference, such as a server error digest or request id. */
  reference?: string;
};

/** A failed load or action. Stays until the user retries or leaves (never auto-dismissed). */
export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  reference,
}: ErrorStateProps) {
  return (
    <StatePanel
      role="alert"
      tone="destructive"
      icon={CircleAlert}
      title={title}
      description={
        <>
          <p>{message}</p>
          {reference ? (
            <p className="mt-2 font-mono text-xs">
              Reference: <span className="select-all">{reference}</span>
            </p>
          ) : null}
        </>
      }
      action={
        onRetry ? (
          <Button type="button" variant="outline" onClick={onRetry}>
            <RotateCw aria-hidden="true" />
            Try again
          </Button>
        ) : null
      }
    />
  );
}
