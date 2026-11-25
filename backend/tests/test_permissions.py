"""Every cell of the permission matrix (guide §3.1)."""

import pytest

from app.core.permissions import ROLE_CAPABILITIES, Capability, Role, has_capability

A, D, R, V = Role.ADMIN, Role.DEVELOPER, Role.REVIEWER, Role.VIEWER

# Capability -> roles that have it, copied from the guide's table.
MATRIX: dict[Capability, set[Role]] = {
    Capability.VIEW: {A, D, R, V},
    Capability.MANAGE_WORKSPACE: {A},
    Capability.MANAGE_GITHUB_INTEGRATION: {A},
    Capability.MANAGE_APPLICATIONS: {A, D},
    Capability.CONFIGURE_ENVIRONMENTS: {A},
    Capability.REGISTER_RELEASES: {A, D},
    Capability.REQUEST_DEPLOYMENTS: {A, D},
    Capability.DECIDE_APPROVALS: {A, R},
    Capability.INITIATE_ROLLBACKS: {A, D},
    Capability.REQUEST_AI_ANALYSIS: {A, D, R, V},
}


def test_matrix_covers_every_capability_and_role() -> None:
    assert set(MATRIX) == set(Capability)
    assert set(ROLE_CAPABILITIES) == set(Role)


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("capability", list(Capability))
def test_role_capability(role: Role, capability: Capability) -> None:
    assert has_capability(role, capability) is (role in MATRIX[capability])


def test_role_capabilities_are_read_only() -> None:
    with pytest.raises(TypeError):
        ROLE_CAPABILITIES[V] = frozenset(Capability)  # type: ignore[index]
