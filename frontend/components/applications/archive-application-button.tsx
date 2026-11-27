"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Archive, CircleAlert, Loader2 } from "lucide-react";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/services/api";
import {
  type Application,
  applicationsQueryKey,
  archiveApplication,
} from "@/services/applications";

export function archiveErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Couldn't reach ReleaseGuard. Check your connection and try again.";
  }
  if (error.status === 403)
    return "Your role in this workspace doesn't allow archiving applications.";
  if (error.status === 404) return "This application no longer exists.";
  if (error.status === 409) return error.message;
  return "The application couldn't be archived. Try again in a moment.";
}

type ArchiveApplicationButtonProps = {
  application: Pick<Application, "id" | "name">;
  size?: "sm" | "default";
};

/**
 * Archive with a confirmation step. Render it only for roles that may archive (a UX nicety:
 * the backend answers 403 otherwise, and the dialog shows that).
 */
export function ArchiveApplicationButton({
  application,
  size = "sm",
}: ArchiveApplicationButtonProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const archive = useMutation({
    mutationFn: () => archiveApplication(application.id),
    onSuccess: async () => {
      setOpen(false);
      await queryClient.invalidateQueries({ queryKey: applicationsQueryKey });
    },
  });

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) archive.reset();
      }}
    >
      <AlertDialogTrigger asChild>
        <Button variant="outline" size={size} aria-label={`Archive ${application.name}`}>
          <Archive aria-hidden="true" />
          Archive
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Archive {application.name}?</AlertDialogTitle>
          <AlertDialogDescription>
            It moves out of the active list and takes no new releases or deployments. Its history
            and audit log stay.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {archive.isError && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
          >
            <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>{archiveErrorMessage(archive.error)}</span>
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={archive.isPending}>Cancel</AlertDialogCancel>
          {/* A plain button, not AlertDialogAction: that one closes the dialog before the request ends. */}
          <Button
            variant="destructive"
            disabled={archive.isPending}
            onClick={() => archive.mutate()}
          >
            {archive.isPending && <Loader2 aria-hidden="true" className="animate-spin" />}
            Archive
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
