import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginForm } from "@/components/auth/login-form";
import { LoadingState } from "@/components/states/loading-state";

export const metadata: Metadata = { title: "Sign in" };

// Outside the (app) route group, so it renders without the sidebar. The form reads `?next=`
// (request-time), hence the Suspense boundary around it.
export default function LoginPage() {
  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Suspense
        fallback={
          <div className="w-full max-w-sm">
            <LoadingState label="Loading sign-in form…" rows={2} />
          </div>
        }
      >
        <LoginForm />
      </Suspense>
    </main>
  );
}
