"""Roles and the capability matrix (guide §3.1).

Pure data with no database access, and the only place the matrix is written down. Routes check it
with ``require_capability`` / ``require_role`` (``app/api/deps.py``) and services again with
``app.services.authz.ensure_can``; services also own workspace scoping and finer rules
(self-approval, a reviewer deciding twice, stale or expired requests).
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class Role(StrEnum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class Capability(StrEnum):
    VIEW = "view"  # dashboard, environments, releases, deployments, audit log
    MANAGE_WORKSPACE = "manage_workspace"  # workspace settings, members and roles
    MANAGE_GITHUB_INTEGRATION = "manage_github_integration"
    MANAGE_APPLICATIONS = "manage_applications"  # create, edit, archive
    CONFIGURE_ENVIRONMENTS = "configure_environments"  # health checks and approval policy
    REGISTER_RELEASES = "register_releases"
    REQUEST_DEPLOYMENTS = "request_deployments"
    DECIDE_APPROVALS = "decide_approvals"  # approve or reject
    INITIATE_ROLLBACKS = "initiate_rollbacks"
    REQUEST_AI_ANALYSIS = "request_ai_analysis"


_EVERYONE = frozenset({Capability.VIEW, Capability.REQUEST_AI_ANALYSIS})

ROLE_CAPABILITIES: Mapping[Role, frozenset[Capability]] = MappingProxyType(
    {
        Role.ADMIN: frozenset(Capability),
        Role.DEVELOPER: _EVERYONE
        | {
            Capability.MANAGE_APPLICATIONS,
            Capability.REGISTER_RELEASES,
            Capability.REQUEST_DEPLOYMENTS,
            Capability.INITIATE_ROLLBACKS,
        },
        Role.REVIEWER: _EVERYONE | {Capability.DECIDE_APPROVALS},
        Role.VIEWER: _EVERYONE,
    }
)


def has_capability(role: Role, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES[role]


def roles_with(capability: Capability) -> frozenset[Role]:
    """The roles that hold ``capability``, derived from the one matrix above."""
    return frozenset(
        role for role, capabilities in ROLE_CAPABILITIES.items() if capability in capabilities
    )
