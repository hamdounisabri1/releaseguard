"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";
import { type Path, useForm } from "react-hook-form";
import { z } from "zod";

import { FormAlert, FormInput } from "@/components/forms/form-input";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Button } from "@/components/ui/button";
import { FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";
import { fieldErrors } from "@/lib/form-errors";
import { ApiError } from "@/services/api";
import { applicationsQueryKey, type Environment } from "@/services/applications";
import { environmentQueryKey, updateEnvironment } from "@/services/environments";

/** A whole number in `[min, max]`; an empty input arrives as `NaN` (`valueAsNumber`). */
function whole(min: number, max: number) {
  return z
    .number({ error: "Enter a number." })
    .int("Use a whole number.")
    .min(min, `Use ${min} or more.`)
    .max(max, `Use ${max} or less.`);
}

// The bounds of `EnvironmentUpdate` in `backend/app/schemas/environments.py`; the backend checks again.
const settingsSchema = z.object({
  expected_status: whole(100, 599),
  check_interval_seconds: whole(10, 86_400),
  timeout_ms: whole(100, 60_000),
  failure_threshold: whole(1, 20),
  verify_successes: whole(1, 20),
  verify_timeout_seconds: whole(10, 3_600),
});

export type SettingsValues = z.infer<typeof settingsSchema>;
type SettingsField = Path<SettingsValues>;

const FIELDS: ReadonlySet<SettingsField> = new Set<SettingsField>([
  "expected_status",
  "check_interval_seconds",
  "timeout_ms",
  "failure_threshold",
  "verify_successes",
  "verify_timeout_seconds",
]);

function toValues(env: Environment): SettingsValues {
  return {
    expected_status: env.expected_status,
    check_interval_seconds: env.check_interval_seconds,
    timeout_ms: env.timeout_ms,
    failure_threshold: env.failure_threshold,
    verify_successes: env.verify_successes,
    verify_timeout_seconds: env.verify_timeout_seconds,
  };
}

/** Only the fields that differ from the saved environment (a PATCH changes only what it sends). */
export function changedSettings(
  saved: Environment,
  values: SettingsValues,
): Partial<SettingsValues> {
  const current = toValues(saved);
  return Object.fromEntries(
    Object.entries(values).filter(([key, value]) => current[key as SettingsField] !== value),
  ) as Partial<SettingsValues>;
}

export function saveErrorMessage(error: unknown, hasFieldErrors: boolean): string | null {
  if (!(error instanceof ApiError)) {
    return "Couldn't reach ReleaseGuard. Check your connection and try again.";
  }
  if (error.status === 422) return hasFieldErrors ? null : "Check the highlighted fields.";
  if (error.status === 404) return "This environment no longer exists.";
  return "The settings couldn't be saved. Try again in a moment.";
}

type EnvironmentSettingsFormProps = { environment: Environment };

/**
 * Health-check and verification settings of one environment (Admin only; the page shows
 * `PermissionDenied` to other roles, and so does this form if the backend answers 403).
 */
export function EnvironmentSettingsForm({ environment }: EnvironmentSettingsFormProps) {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const form = useForm<SettingsValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: toValues(environment),
  });
  const save = useMutation({
    mutationFn: (body: Partial<SettingsValues>) => updateEnvironment(environment.id, body),
    onSuccess: async (updated) => {
      queryClient.setQueryData(environmentQueryKey(updated.id), updated);
      form.reset(toValues(updated));
      setSaved(true);
      await queryClient.invalidateQueries({ queryKey: applicationsQueryKey });
    },
    onError: (error) => {
      const byField = fieldErrors(error, FIELDS);
      for (const [field, message] of byField) form.setError(field, { message });
      setFormError(saveErrorMessage(error, byField.length > 0));
    },
  });

  if (save.error instanceof ApiError && save.error.status === 403) {
    return <PermissionDenied what="change environment settings" />;
  }

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null);
    setSaved(false);
    const changes = changedSettings(environment, values);
    if (Object.keys(changes).length === 0) return;
    save.mutate(changes);
  });
  const { errors, isDirty } = form.formState;
  const number = { type: "number", inputMode: "numeric", step: 1 } as const;
  const register = (field: SettingsField) => form.register(field, { valueAsNumber: true });

  return (
    <form
      noValidate
      onSubmit={onSubmit}
      aria-describedby={formError ? "settings-error" : undefined}
      className="max-w-2xl"
    >
      <FieldGroup>
        {formError ? <FormAlert id="settings-error">{formError}</FormAlert> : null}
        <FormInput
          id="env-health-url"
          label="Health URL"
          value={environment.health_url ?? ""}
          placeholder="Not set"
          readOnly
          disabled
          description="Read-only for now: health URLs become editable together with the address safety checks that guard them."
        />
        <FieldSet>
          <FieldLegend>Health check</FieldLegend>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormInput
              id="env-expected-status"
              label="Expected status"
              description="HTTP status a healthy check returns (100–599)."
              error={errors.expected_status}
              {...number}
              {...register("expected_status")}
            />
            <FormInput
              id="env-interval"
              label="Check interval (seconds)"
              description="Time between checks (10–86400)."
              error={errors.check_interval_seconds}
              {...number}
              {...register("check_interval_seconds")}
            />
            <FormInput
              id="env-timeout"
              label="Timeout (ms)"
              description="How long one check may take (100–60000)."
              error={errors.timeout_ms}
              {...number}
              {...register("timeout_ms")}
            />
            <FormInput
              id="env-failure-threshold"
              label="Failure threshold"
              description="Failed checks in a row before the environment is Unhealthy (1–20)."
              error={errors.failure_threshold}
              {...number}
              {...register("failure_threshold")}
            />
          </div>
        </FieldSet>
        <FieldSet>
          <FieldLegend>Verification rule</FieldLegend>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormInput
              id="env-verify-successes"
              label="Healthy checks required"
              description="Healthy checks in a row that verify a deployment (1–20)."
              error={errors.verify_successes}
              {...number}
              {...register("verify_successes")}
            />
            <FormInput
              id="env-verify-timeout"
              label="Verification timeout (seconds)"
              description="A deployment not verified by then is Unhealthy (10–3600)."
              error={errors.verify_timeout_seconds}
              {...number}
              {...register("verify_timeout_seconds")}
            />
          </div>
        </FieldSet>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={save.isPending || !isDirty}>
            {save.isPending ? <Loader2 aria-hidden="true" className="animate-spin" /> : null}
            {save.isPending ? "Saving…" : "Save settings"}
          </Button>
          <p role="status" className="flex items-center gap-1.5 text-sm text-muted-foreground">
            {saved && !isDirty ? (
              <>
                <CheckCircle2 aria-hidden="true" className="size-4 text-emerald-600" />
                Settings saved.
              </>
            ) : null}
          </p>
        </div>
      </FieldGroup>
    </form>
  );
}
