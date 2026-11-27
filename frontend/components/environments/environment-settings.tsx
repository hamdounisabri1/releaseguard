"use client";

import { useQuery } from "@tanstack/react-query";
import { Archive, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { environmentLabel, HealthBadge } from "@/components/environments/environment-labels";
import { EnvironmentSettingsForm } from "@/components/environments/environment-settings-form";
import { ApiErrorState } from "@/components/states/api-error-state";
import { EmptyState } from "@/components/states/empty-state";
import { LoadingState } from "@/components/states/loading-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Button } from "@/components/ui/button";
import { can } from "@/lib/permissions";
import { ApiError } from "@/services/api";
import { applicationQueryOptions } from "@/services/applications";
import { meQueryOptions } from "@/services/auth";
import { environmentQueryOptions } from "@/services/environments";

const NOT_FOUND = new ApiError(404, "not_found", "This environment doesn't exist.");

/** Settings page of one environment: Admins edit it, everyone else gets the permission-denied state. */
export function EnvironmentSettings() {
  const { applicationId, environmentId } = useParams<{
    applicationId: string;
    environmentId: string;
  }>();
  const { data: me } = useQuery(meQueryOptions);
  const allowed = can(me?.role, "configure_environments");
  const environment = useQuery({ ...environmentQueryOptions(environmentId), enabled: allowed });
  const application = useQuery({ ...applicationQueryOptions(applicationId), enabled: allowed });

  const back = (
    <div>
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link href={`/applications/${applicationId}`}>
          <ArrowLeft aria-hidden="true" />
          {application.data?.name ?? "Application"}
        </Link>
      </Button>
    </div>
  );

  if (!me) return <LoadingState label="Loading…" />;
  if (!allowed) {
    return (
      <>
        {back}
        <PermissionDenied what="change environment settings" />
      </>
    );
  }
  if (environment.isPending) return <LoadingState label="Loading environment…" />;
  // A failed background refetch keeps the form (and unsaved input) on screen (frontend.md).
  if (environment.data === undefined) {
    return <ApiErrorState error={environment.error} onRetry={() => void environment.refetch()} />;
  }
  const env = environment.data;
  // The URL names both ids; an environment of another application is "not found" here.
  if (env.application_id !== applicationId) return <ApiErrorState error={NOT_FOUND} />;
  // The backend refuses changes to an archived application's environments (409).
  if (application.data?.status === "archived") {
    return (
      <>
        {back}
        <EmptyState
          icon={Archive}
          title="This application is archived"
          description="Its environments keep their settings and history, but they can't be changed."
        />
      </>
    );
  }

  return (
    <>
      {back}
      <section className="flex flex-col gap-1">
        <h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight">
          {environmentLabel(env.environment_type)} settings
          <HealthBadge status={env.health_status} />
        </h1>
        <p className="text-sm text-muted-foreground">
          How ReleaseGuard checks this environment&apos;s health and when it counts a deployment as
          verified.
        </p>
      </section>
      <EnvironmentSettingsForm key={env.id} environment={env} />
    </>
  );
}
