import { SearchX } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Button } from "@/components/ui/button";
import { isRetryable } from "@/lib/query-client";
import { ApiError } from "@/services/api";

const GENERIC_MESSAGE = "This page couldn't be loaded. Try again in a moment.";

type ApiErrorStateProps = {
  /** Whatever was thrown: an `ApiError` from `services/api`, or anything else. */
  error: unknown;
  onRetry?: () => void;
};

/**
 * Picks the right state for a failed request: 401 → (the client is already redirecting to the
 * login page), 403 → permission denied, 404 → not found, anything else → the error message
 * with a retry. Use it for any query's `error`, and in `error.tsx` boundaries.
 */
export function ApiErrorState({ error, onRetry }: ApiErrorStateProps) {
  if (error instanceof ApiError) {
    if (error.status === 401) return <LoadingState label="Redirecting to sign in…" rows={1} />;
    if (error.status === 403) return <PermissionDenied />;
    if (error.status === 404) {
      return (
        <EmptyState
          icon={SearchX}
          title="Not found"
          description={error.message}
          action={
            <Button asChild variant="outline">
              <Link href="/dashboard">Back to dashboard</Link>
            </Button>
          }
        />
      );
    }
    // Same rule as the automatic retries: a 5xx or 429 might pass later, another 4xx won't.
    return (
      <ErrorState message={error.message} onRetry={isRetryable(error) ? onRetry : undefined} />
    );
  }
  // Server Component errors reach the browser as a generic Error with a digest (Next.js hides
  // the message); show the digest so it can be matched with the server logs.
  const digest =
    error instanceof Error && "digest" in error && typeof error.digest === "string"
      ? error.digest
      : undefined;
  return <ErrorState message={GENERIC_MESSAGE} onRetry={onRetry} reference={digest} />;
}
