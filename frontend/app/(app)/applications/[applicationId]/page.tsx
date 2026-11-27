import type { Metadata } from "next";
import { Suspense } from "react";

import { ApplicationDetails } from "@/components/applications/application-details";
import { LoadingState } from "@/components/states/loading-state";

export const metadata: Metadata = { title: "Application" };

// The id is only known at request time, so `useParams()` must sit behind a Suspense boundary
// (Cache Components; see frontend.md).
export default function ApplicationPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading application…" />}>
      <ApplicationDetails />
    </Suspense>
  );
}
