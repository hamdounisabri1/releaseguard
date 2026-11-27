"use client";

import { useQuery } from "@tanstack/react-query";
import { Package, Search, SearchX } from "lucide-react";
import Link from "next/link";
import { useId, useState } from "react";

import { ApplicationStatusBadge } from "@/components/applications/application-status-badge";
import { ArchiveApplicationButton } from "@/components/applications/archive-application-button";
import { CreateApplicationDialog } from "@/components/applications/create-application-dialog";
import { ApiErrorState } from "@/components/states/api-error-state";
import { EmptyState } from "@/components/states/empty-state";
import { LoadingState } from "@/components/states/loading-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";
import { can } from "@/lib/permissions";
import { type Application, applicationsQueryOptions } from "@/services/applications";
import { meQueryOptions } from "@/services/auth";

/** Case-insensitive match on name, description and `owner/name`. */
export function matchesSearch(application: Application, search: string): boolean {
  const needle = search.trim().toLowerCase();
  if (!needle) return true;
  return [
    application.name,
    application.description,
    `${application.repository_owner}/${application.repository_name}`,
  ].some((text) => text.toLowerCase().includes(needle));
}

/** Applications in the workspace: search, show archived, create and archive (by role). */
export function ApplicationsList() {
  const searchId = useId();
  const archivedId = useId();
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const { data: me } = useQuery(meQueryOptions);
  const canManage = can(me?.role, "manage_applications");
  const query = useQuery(applicationsQueryOptions(includeArchived));

  const visible = query.data?.items.filter((app) => matchesSearch(app, search)) ?? [];

  return (
    <>
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Applications</h1>
          <p className="text-sm text-muted-foreground">
            Each application is one GitHub repository with development, staging and production
            environments.
          </p>
        </div>
        {canManage ? <CreateApplicationDialog /> : null}
      </section>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="relative w-full sm:max-w-xs">
          <Label htmlFor={searchId} className="sr-only">
            Search applications
          </Label>
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id={searchId}
            type="search"
            placeholder="Search by name or repository"
            className="pl-8"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <Switch id={archivedId} checked={includeArchived} onCheckedChange={setIncludeArchived} />
          <Label htmlFor={archivedId}>Show archived</Label>
        </div>
      </div>

      {query.isPending ? (
        <LoadingState label="Loading applications…" />
      ) : query.isError ? (
        <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.items.length === 0 ? (
        <EmptyState
          icon={Package}
          title="No applications yet"
          description={
            canManage
              ? "Use New application to link a GitHub repository and its environments."
              : "An Admin or Developer can create the first one."
          }
        />
      ) : visible.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No matching applications"
          description={`Nothing matches “${search.trim()}”.`}
        />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="hidden sm:table-cell">Repository</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Created</TableHead>
                {canManage ? (
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                ) : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((app) => (
                <TableRow key={app.id}>
                  <TableCell className="max-w-64 whitespace-normal">
                    <Link
                      href={`/applications/${app.id}`}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {app.name}
                    </Link>
                    {app.description ? (
                      <p className="truncate text-xs text-muted-foreground">{app.description}</p>
                    ) : null}
                    <p className="truncate font-mono text-xs text-muted-foreground sm:hidden">
                      {app.repository_owner}/{app.repository_name}
                    </p>
                  </TableCell>
                  <TableCell className="hidden font-mono text-xs sm:table-cell">
                    {app.repository_owner}/{app.repository_name}
                  </TableCell>
                  <TableCell>
                    <ApplicationStatusBadge status={app.status} />
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground md:table-cell">
                    <time dateTime={app.created_at}>{formatDateTime(app.created_at)}</time>
                  </TableCell>
                  {canManage ? (
                    <TableCell className="text-right">
                      {app.status === "active" ? (
                        <ArchiveApplicationButton application={app} />
                      ) : null}
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
