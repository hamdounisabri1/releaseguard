"use client";

import { useQuery } from "@tanstack/react-query";
import { Layers } from "lucide-react";

import {
  byPromotionOrder,
  environmentLabel,
  HealthBadge,
} from "@/components/environments/environment-labels";
import { ApiErrorState } from "@/components/states/api-error-state";
import { EmptyState } from "@/components/states/empty-state";
import { LoadingState } from "@/components/states/loading-state";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";
import { applicationEnvironmentsQueryOptions, type Environment } from "@/services/applications";

function Setting({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

type EnvironmentCardProps = {
  environment: Environment;
  /** Shown in the card header, e.g. the "Configure" link for Admins. */
  action?: React.ReactNode;
};

function EnvironmentCard({ environment: env, action }: EnvironmentCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h3 className="flex items-center gap-2">
            {environmentLabel(env.environment_type)}
            <HealthBadge status={env.health_status} />
          </h3>
        </CardTitle>
        {action ? <CardAction>{action}</CardAction> : null}
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3 sm:grid-cols-2">
          <Setting label="Health URL">
            {env.health_url ? (
              <span className="font-mono text-xs break-all">{env.health_url}</span>
            ) : (
              <span className="text-muted-foreground">Not set</span>
            )}
          </Setting>
          <Setting label="Expected status">{env.expected_status}</Setting>
          <Setting label="Check every">{env.check_interval_seconds} s</Setting>
          <Setting label="Timeout">{env.timeout_ms} ms</Setting>
          <Setting label="Unhealthy after">
            {env.failure_threshold} failed {env.failure_threshold === 1 ? "check" : "checks"}
          </Setting>
          <Setting label="Verified after">
            {env.verify_successes} healthy {env.verify_successes === 1 ? "check" : "checks"} within{" "}
            {env.verify_timeout_seconds} s
          </Setting>
          <Setting label="Approval">
            {env.policy.requires_approval ? "Required" : "Not required"}
          </Setting>
          <Setting label="Last checked">
            {env.last_checked_at ? (
              <time dateTime={env.last_checked_at}>{formatDateTime(env.last_checked_at)}</time>
            ) : (
              <span className="text-muted-foreground">Never</span>
            )}
          </Setting>
        </dl>
      </CardContent>
    </Card>
  );
}

type EnvironmentsTabProps = {
  applicationId: string;
  /** Per-environment header action (rendered only for roles that may use it). */
  renderAction?: (environment: Environment) => React.ReactNode;
};

/** The application's three environments with their health-check settings and health. */
export function EnvironmentsTab({ applicationId, renderAction }: EnvironmentsTabProps) {
  const query = useQuery(applicationEnvironmentsQueryOptions(applicationId));
  if (query.isPending) return <LoadingState label="Loading environments…" />;
  if (query.isError) {
    return <ApiErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (query.data.length === 0) {
    return (
      <EmptyState
        icon={Layers}
        title="No environments"
        description="This application has no environments."
      />
    );
  }
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {query.data.toSorted(byPromotionOrder).map((env) => (
        <EnvironmentCard key={env.id} environment={env} action={renderAction?.(env)} />
      ))}
    </div>
  );
}
