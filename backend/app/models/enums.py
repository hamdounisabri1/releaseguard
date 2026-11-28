"""Values stored in status, type and role columns. Each one has a matching CHECK constraint
(built with ``app.db.base.check_in``), so the database and Python agree.
"""

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ApplicationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class EnvironmentType(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class HealthStatus(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class ActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    CI = "ci"


class ReleaseSource(StrEnum):
    CI = "ci"
    MANUAL = "manual"


class OperationType(StrEnum):
    DEPLOY = "deploy"
    ROLLBACK = "rollback"


class DeploymentStatus(StrEnum):
    """Deployment states (guide §8). Only ``deployment_service.transition`` changes them."""

    AWAITING_APPROVAL = "awaiting_approval"
    QUEUED = "queued"
    DEPLOYING = "deploying"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNHEALTHY = "unhealthy"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# At most one deployment per environment in these states: the partial unique index
# ``deployments_one_active_per_env`` lists the same values.
ACTIVE_STATUSES: frozenset[DeploymentStatus] = frozenset(
    {DeploymentStatus.QUEUED, DeploymentStatus.DEPLOYING, DeploymentStatus.VERIFYING}
)


class DeploymentErrorCode(StrEnum):
    DISPATCH_FAILED = "dispatch_failed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    RUN_NOT_FOUND = "run_not_found"


class EventSource(StrEnum):
    """Who moved a deployment: a person, the environment policy, a webhook or the worker."""

    USER = "user"
    POLICY = "policy"
    WEBHOOK = "webhook"
    WORKER = "worker"


class IntegrationProvider(StrEnum):
    GITHUB = "github"


class IntegrationStatus(StrEnum):
    """``pending`` until the worker confirms the installation with GitHub; ``invalid`` when it
    doesn't exist for our App; ``disconnected`` after an Admin removes it.
    """

    PENDING = "pending"
    ACTIVE = "active"
    INVALID = "invalid"
    DISCONNECTED = "disconnected"


# An installation in one of these states belongs to its workspace: no other workspace can link it,
# and the workspace can't link a second one.
LINKED_INTEGRATION_STATUSES: frozenset[IntegrationStatus] = frozenset(
    {IntegrationStatus.PENDING, IntegrationStatus.ACTIVE}
)


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    DEAD = "dead"
