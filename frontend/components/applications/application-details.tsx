"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, Settings2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ApplicationStatusBadge } from "@/components/applications/application-status-badge";
import { ArchiveApplicationButton } from "@/components/applications/archive-application-button";
import { environmentLabel } from "@/components/environments/environment-labels";
import { EnvironmentsTab } from "@/components/environments/environments-tab";
import { ApiErrorState } from "@/components/states/api-error-state";
import { LoadingState } from "@/components/states/loading-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDateTime } from "@/lib/format";
import { can } from "@/lib/permissions";
import { type Application, applicationQueryOptions } from "@/services/applications";
import { meQueryOptions } from "@/services/auth";

function RepositorySettings({ application: app }: { application: Application }) {
  const rows: Array<[string, React.ReactNode]> = [
    ["Repository", `${app.repository_owner}/${app.repository_name}`],
    ["Repository id", app.repository_id ?? "Not linked yet"],
    ["Default branch", app.default_branch],
    ["CI workflow", app.ci_workflow_path],
    ["Deploy workflow", app.deploy_workflow_path],
  ];
  return (
    <Card>
      <CardContent>
        <dl className="grid gap-3 sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div key={label} className="flex flex-col gap-0.5">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="font-mono text-sm break-all">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

/** One application: header, archive (by role) and tabs for its environments and repository. */
export function ApplicationDetails() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const { data: me } = useQuery(meQueryOptions);
  const canManage = can(me?.role, "manage_applications");
  const canConfigure = can(me?.role, "configure_environments");
  const query = useQuery(applicationQueryOptions(applicationId));

  if (query.isPending) return <LoadingState label="Loading application…" />;
  if (query.isError) {
    return <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const app = query.data;
  const repoUrl = `https://github.com/${app.repository_owner}/${app.repository_name}`;
  return (
    <>
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link href="/applications">
            <ArrowLeft aria-hidden="true" />
            Applications
          </Link>
        </Button>
      </div>
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight">
            <span className="break-words">{app.name}</span>
            <ApplicationStatusBadge status={app.status} />
          </h1>
          {app.description ? (
            <p className="text-sm text-muted-foreground">{app.description}</p>
          ) : null}
          <p className="flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
            <a
              href={repoUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 font-mono text-xs underline-offset-4 hover:underline"
            >
              {app.repository_owner}/{app.repository_name}
              <ExternalLink aria-hidden="true" className="size-3" />
              <span className="sr-only">(opens GitHub in a new tab)</span>
            </a>
            <span>
              Created <time dateTime={app.created_at}>{formatDateTime(app.created_at)}</time>
            </span>
            {app.archived_at ? (
              <span>
                Archived <time dateTime={app.archived_at}>{formatDateTime(app.archived_at)}</time>
              </span>
            ) : null}
          </p>
        </div>
        {canManage && app.status === "active" ? (
          <ArchiveApplicationButton application={app} size="default" />
        ) : null}
      </section>

      <Tabs defaultValue="environments">
        <TabsList>
          <TabsTrigger value="environments">Environments</TabsTrigger>
          <TabsTrigger value="repository">Repository</TabsTrigger>
        </TabsList>
        <TabsContent value="environments" className="pt-2">
          <EnvironmentsTab
            applicationId={app.id}
            renderAction={
              canConfigure
                ? (env) => (
                    <Button asChild variant="outline" size="sm">
                      <Link
                        href={`/applications/${app.id}/environments/${env.id}`}
                        aria-label={`Configure ${environmentLabel(env.environment_type)}`}
                      >
                        <Settings2 aria-hidden="true" />
                        Configure
                      </Link>
                    </Button>
                  )
                : undefined
            }
          />
        </TabsContent>
        <TabsContent value="repository" className="pt-2">
          <RepositorySettings application={app} />
        </TabsContent>
      </Tabs>
    </>
  );
}
