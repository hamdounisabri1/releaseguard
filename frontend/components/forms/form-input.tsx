import { CircleAlert } from "lucide-react";
import type { FieldError as HookFieldError } from "react-hook-form";

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

type FormInputProps = React.ComponentProps<typeof Input> & {
  id: string;
  label: string;
  /** Help text under the field (bounds, units). */
  description?: React.ReactNode;
  /** The field's error, from the Zod schema or a server 422 (`setError`). */
  error?: HookFieldError;
};

/** Label, input, help text and the inline error, wired for screen readers. */
export function FormInput({ id, label, description, error, ...input }: FormInputProps) {
  const describedBy = [description ? `${id}-description` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(" ");
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        {...input}
      />
      {description ? (
        <FieldDescription id={`${id}-description`}>{description}</FieldDescription>
      ) : null}
      <FieldError id={`${id}-error`} errors={[error]} />
    </Field>
  );
}

/** A form-level error (not tied to one field). Stays on screen; announced at once. */
export function FormAlert({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <div
      id={id}
      role="alert"
      className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
    >
      <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <p>{children}</p>
    </div>
  );
}
