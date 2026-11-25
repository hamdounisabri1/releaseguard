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
