import { Badge } from "@/components/ui/badge";
import type { Environment } from "@/services/applications";

type EnvironmentType = Environment["environment_type"];
type HealthStatus = Environment["health_status"];

const TYPE_LABELS: Record<EnvironmentType, string> = {
  development: "Development",
  staging: "Staging",
  production: "Production",
};

const TYPE_ORDER: Record<EnvironmentType, number> = { development: 0, staging: 1, production: 2 };

export function environmentLabel(type: EnvironmentType): string {
  return TYPE_LABELS[type];
}

/** Development, staging, production: the order a release is promoted in. */
export function byPromotionOrder(a: Environment, b: Environment): number {
  return TYPE_ORDER[a.environment_type] - TYPE_ORDER[b.environment_type];
}

const HEALTH: Record<HealthStatus, { label: string; className: string }> = {
  healthy: {
    label: "Healthy",
    className:
      "border-emerald-600/30 bg-emerald-600/10 text-emerald-700 dark:border-emerald-400/30 dark:text-emerald-300",
  },
  unhealthy: {
    label: "Unhealthy",
    className:
      "border-amber-600/30 bg-amber-500/10 text-amber-800 dark:border-amber-400/30 dark:text-amber-300",
  },
  unknown: { label: "Unknown", className: "text-muted-foreground" },
};

/**
 * Environment health (from health checks). Its own badge, kept apart from deployment status:
 * a deployment can succeed while the environment is unhealthy (frontend.md).
 */
export function HealthBadge({ status }: { status: HealthStatus }) {
  const { label, className } = HEALTH[status];
  return (
    <Badge variant="outline" className={className}>
      <span className="sr-only">Health: </span>
      {label}
    </Badge>
  );
}
