"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Loader2, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { type Path, useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { safeNextPath } from "@/lib/auth-routes";
import { fieldErrors } from "@/lib/form-errors";
import { loginRedirectBounced, markLoginRedirect } from "@/lib/login-redirect";
import { ApiError } from "@/services/api";
import { login, meQueryKey, meQueryOptions } from "@/services/auth";

const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter your email address.")
    // Only a sanity check: the backend decides. Stricter rules would lock out valid accounts
    // such as `admin@localhost`.
    .refine((email) => /^[^@\s]+@[^@\s]+$/.test(email), "Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type LoginValues = z.infer<typeof loginSchema>;

const FIELDS: ReadonlySet<Path<LoginValues>> = new Set<Path<LoginValues>>(["email", "password"]);

/** The message above the button for a failed sign-in; `null` when the error belongs to a field. */
export function loginErrorMessage(error: unknown, hasFieldErrors = false): string | null {
  if (!(error instanceof ApiError)) {
    return "Couldn't reach ReleaseGuard. Check your connection and try again.";
  }
  if (error.status === 401) return "Email or password is incorrect.";
  // The backend's message says to wait; `Retry-After` has the seconds.
  if (error.status === 429) return error.message;
  if (error.status === 422) return hasFieldErrors ? null : "Check your email and password.";
  if (error.status === 403)
    return "Sign-in was refused for this site. Reload the page and try again.";
  return "Sign-in isn't available right now. Try again in a moment.";
}

/** Email + password sign-in; on success goes to `?next=` (same-site paths only) or the dashboard. */
export function LoginForm() {
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));
  const queryClient = useQueryClient();
  const alertRef = useRef<HTMLDivElement>(null);
  const [formError, setFormError] = useState<string | null>(null);
  // Read once per visit: did our own redirect away from here just bounce back? (lib/login-redirect)
  const [bounced] = useState(loginRedirectBounced);

  // Already signed in (or just signed in: the mutation fills this query): leave the login page.
  // Without a session this is a 401, which the API client ignores on the login page.
  const me = useQuery(meQueryOptions);
  const stuck = me.isSuccess && bounced;
  useEffect(() => {
    if (!me.isSuccess || bounced) return;
    markLoginRedirect();
    router.replace(next);
  }, [me.isSuccess, bounced, next, router]);

  useEffect(() => {
    if (formError) alertRef.current?.focus();
  }, [formError]);

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
    defaultValues: { email: "", password: "" },
  });
  const { errors } = form.formState;

  const signIn = useMutation({
    mutationFn: login,
    onSuccess: (user) => queryClient.setQueryData(meQueryKey, user),
    onError: (error) => {
      const byField = fieldErrors(error, FIELDS);
      for (const [field, message] of byField) form.setError(field, { message });
      setFormError(loginErrorMessage(error, byField.length > 0));
      form.resetField("password");
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null);
    signIn.mutate(values);
  });
  const busy = (signIn.isPending || signIn.isSuccess) && !stuck;
  const shownError = stuck
    ? "You're signed in, but this site can't see the session cookie. Open ReleaseGuard on the same host as its API (for example localhost for both), then reload."
    : formError;

  return (
    <Card className="w-full max-w-sm">
      <CardHeader className="items-center text-center">
        <span className="mx-auto mb-2 flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <ShieldCheck aria-hidden="true" />
        </span>
        <CardTitle>
          <h1 className="text-xl font-semibold tracking-tight">Sign in to ReleaseGuard</h1>
        </CardTitle>
        <CardDescription>Use your work email and password.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          noValidate
          onSubmit={onSubmit}
          aria-describedby={shownError ? "login-error" : undefined}
        >
          <FieldGroup>
            {shownError ? (
              <div
                ref={alertRef}
                id="login-error"
                role="alert"
                tabIndex={-1}
                className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive outline-none focus-visible:ring-3 focus-visible:ring-destructive/30"
              >
                <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                <p>{shownError}</p>
              </div>
            ) : null}
            <Field data-invalid={errors.email ? true : undefined}>
              <FieldLabel htmlFor="email">Email</FieldLabel>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                inputMode="email"
                spellCheck={false}
                autoFocus
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={errors.email ? "email-error" : undefined}
                {...form.register("email")}
              />
              <FieldError id="email-error" errors={[errors.email]} />
            </Field>
            <Field data-invalid={errors.password ? true : undefined}>
              <FieldLabel htmlFor="password">Password</FieldLabel>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={errors.password ? true : undefined}
                aria-describedby={errors.password ? "password-error" : undefined}
                {...form.register("password")}
              />
              <FieldError id="password-error" errors={[errors.password]} />
            </Field>
            <Button type="submit" className="h-10 w-full" disabled={busy}>
              {busy ? <Loader2 aria-hidden="true" className="animate-spin" /> : null}
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
