"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";

import { ApiErrorState } from "@/components/states/api-error-state";

/** Error boundary for every page in the app shell: the shell stays, the page shows the error. */
export default function AppError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return <ApiErrorState error={error} onRetry={retry} />;
}
