import type { Metadata } from "next";
import { Suspense } from "react";

import { EnvironmentSettings } from "@/components/environments/environment-settings";
import { LoadingState } from "@/components/states/loading-state";

export const metadata: Metadata = { title: "Environment settings" };

// The ids are only known at request time, so `useParams()` sits behind a Suspense boundary.
export default function EnvironmentSettingsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading environment…" />}>
      <EnvironmentSettings />
    </Suspense>
  );
}
