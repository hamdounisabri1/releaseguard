"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { type Path, useForm } from "react-hook-form";
import { z } from "zod";

import { FormAlert, FormInput } from "@/components/forms/form-input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { FieldGroup } from "@/components/ui/field";
import { fieldErrors } from "@/lib/form-errors";
import { ApiError } from "@/services/api";
import { applicationsQueryKey, createApplication } from "@/services/applications";

// The same rules as `backend/app/schemas/applications.py`; the backend checks again.
const createSchema = z.object({
  name: z.string().trim().min(1, "Enter a name.").max(100, "Use at most 100 characters."),
  repository_owner: z
    .string()
    .trim()
    .regex(/^[A-Za-z0-9][A-Za-z0-9-]{0,38}$/, "Enter a GitHub user or organization name."),
  repository_name: z
    .string()
    .trim()
    .regex(/^[A-Za-z0-9._-]{1,100}$/, "Enter a GitHub repository name."),
  description: z.string().trim().max(500, "Use at most 500 characters."),
  default_branch: z
    .string()
    .trim()
    .min(1, "Enter the default branch.")
    .max(255, "Use at most 255 characters.")
    .regex(/^[^\s~^:?*[\\-][^\s~^:?*[\\]*$/, "Enter a valid branch name."),
  ci_workflow_path: z
    .string()
    .trim()
    .max(255, "Use at most 255 characters.")
    .regex(/^\.github\/workflows\/[A-Za-z0-9._-]+\.ya?ml$/, "Use .github/workflows/<file>.yml."),
  deploy_workflow_path: z
    .string()
    .trim()
    .max(255, "Use at most 255 characters.")
    .regex(/^\.github\/workflows\/[A-Za-z0-9._-]+\.ya?ml$/, "Use .github/workflows/<file>.yml."),
});

type CreateValues = z.infer<typeof createSchema>;

const FIELDS: ReadonlySet<Path<CreateValues>> = new Set<Path<CreateValues>>([
  "name",
  "repository_owner",
  "repository_name",
  "description",
  "default_branch",
  "ci_workflow_path",
  "deploy_workflow_path",
]);

const DEFAULTS: CreateValues = {
  name: "",
  repository_owner: "",
  repository_name: "",
  description: "",
  default_branch: "main",
  ci_workflow_path: ".github/workflows/ci.yml",
  deploy_workflow_path: ".github/workflows/deploy.yml",
};

/** The message above the buttons for a failed create; `null` when the error belongs to a field. */
export function createErrorMessage(error: unknown, hasFieldErrors: boolean): string | null {
  if (!(error instanceof ApiError)) {
    return "Couldn't reach ReleaseGuard. Check your connection and try again.";
  }
  if (error.status === 403)
    return "Your role in this workspace doesn't allow creating applications.";
  if (error.status === 409 && error.code === "repository_already_registered") return null;
  if (error.status === 409) return error.message;
  if (error.status === 422) return hasFieldErrors ? null : "Check the highlighted fields.";
  return "The application couldn't be created. Try again in a moment.";
}

/**
 * "New application" button and form. On success it opens the new application, whose three
 * environments the backend has just created. Render it only for roles that may create.
 */
export function CreateApplicationDialog() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: DEFAULTS,
  });
  const create = useMutation({
    mutationFn: createApplication,
    onSuccess: async (application) => {
      await queryClient.invalidateQueries({ queryKey: applicationsQueryKey });
      setOpen(false);
      router.push(`/applications/${application.id}`);
    },
    onError: (error) => {
      const byField = fieldErrors(error, FIELDS);
      for (const [field, message] of byField) form.setError(field, { message });
      if (error instanceof ApiError && error.code === "repository_already_registered") {
        form.setError("repository_name", { message: error.message });
      }
      setFormError(createErrorMessage(error, byField.length > 0));
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null);
    create.mutate(values);
  });
  const { errors } = form.formState;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          form.reset(DEFAULTS);
          setFormError(null);
          create.reset();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus aria-hidden="true" />
          New application
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New application</DialogTitle>
          <DialogDescription>
            Link a GitHub repository. Development, staging and production environments are created
            with it.
          </DialogDescription>
        </DialogHeader>
        <form
          noValidate
          onSubmit={onSubmit}
          aria-describedby={formError ? "create-error" : undefined}
        >
          <FieldGroup>
            {formError ? <FormAlert id="create-error">{formError}</FormAlert> : null}
            <FormInput
              id="app-name"
              label="Name"
              autoComplete="off"
              error={errors.name}
              {...form.register("name")}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <FormInput
                id="app-repository-owner"
                label="Repository owner"
                placeholder="acme"
                autoComplete="off"
                spellCheck={false}
                error={errors.repository_owner}
                {...form.register("repository_owner")}
              />
              <FormInput
                id="app-repository-name"
                label="Repository name"
                placeholder="taskflow"
                autoComplete="off"
                spellCheck={false}
                error={errors.repository_name}
                {...form.register("repository_name")}
              />
            </div>
            <FormInput
              id="app-description"
              label="Description (optional)"
              autoComplete="off"
              error={errors.description}
              {...form.register("description")}
            />
            <FormInput
              id="app-default-branch"
              label="Default branch"
              spellCheck={false}
              error={errors.default_branch}
              {...form.register("default_branch")}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <FormInput
                id="app-ci-workflow"
                label="CI workflow"
                spellCheck={false}
                error={errors.ci_workflow_path}
                {...form.register("ci_workflow_path")}
              />
              <FormInput
                id="app-deploy-workflow"
                label="Deploy workflow"
                spellCheck={false}
                error={errors.deploy_workflow_path}
                {...form.register("deploy_workflow_path")}
              />
            </div>
          </FieldGroup>
          <DialogFooter className="mt-6">
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={create.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? <Loader2 aria-hidden="true" className="animate-spin" /> : null}
              {create.isPending ? "Creating…" : "Create application"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
