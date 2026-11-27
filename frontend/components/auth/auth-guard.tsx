"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { ApiErrorState } from "@/components/states/api-error-state";
import { LoadingState } from "@/components/states/loading-state";
import { clearLoginRedirect } from "@/lib/login-redirect";
import { meQueryOptions } from "@/services/auth";

/**
 * Renders app pages only for a valid session. `proxy.ts` already sent visitors without a cookie
 * to the login page; this asks the backend (`GET /auth/me`) whether the cookie is still a live
 * session. A 401 makes the API client redirect to `/login?next=…`, and `ApiErrorState` shows
 * "Redirecting…" meanwhile; a 5xx or network error shows a retry. The backend enforces every
 * permission regardless.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const me = useQuery(meQueryOptions);
  const signedIn = Boolean(me.data);
  // The session reached an app page, so the login page's redirect didn't bounce.
  useEffect(() => {
    if (signedIn) clearLoginRedirect();
  }, [signedIn]);

  // Data first: a failed *background* refetch keeps the confirmed session's data, and must not
  // swap the page (and any unsaved input) for an error. A 401 still redirects via the API client.
  if (me.data) return children;
  if (me.isError) return <ApiErrorState error={me.error} onRetry={() => void me.refetch()} />;
  return <LoadingState label="Checking your session…" />;
}
