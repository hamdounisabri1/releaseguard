"""Sprint 2 schema against real Postgres (SCRUM-36): the single-active-deployment index,
append-only deployment events, release identity and the job de-duplication key.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Deployment, DeploymentEvent, Job
from app.models.deployments import ONE_ACTIVE_PER_ENVIRONMENT
from app.models.enums import (
    ACTIVE_STATUSES,
    DeploymentStatus,
    EnvironmentType,
    EventSource,
    OperationType,
)
from tests.factories import (
    make_application,
    make_deployment,
    make_environment,
    make_release,
    make_workspace,
)


@pytest.mark.parametrize("active", sorted(ACTIVE_STATUSES))
def test_a_second_active_deployment_in_one_environment_is_refused(
    db: Session, active: DeploymentStatus
) -> None:
    application = make_application(db, make_workspace(db))
    release = make_release(db, application)
    environment = make_environment(db, application)
    make_deployment(db, release, environment, DeploymentStatus.QUEUED)

    with pytest.raises(IntegrityError, match=ONE_ACTIVE_PER_ENVIRONMENT):
        make_deployment(db, release, environment, active)


def test_terminal_deployments_and_other_environments_do_not_block(db: Session) -> None:
    application = make_application(db, make_workspace(db))
    release = make_release(db, application)
    development = make_environment(db, application, EnvironmentType.DEVELOPMENT)
    staging = make_environment(db, application, EnvironmentType.STAGING)
    for status in (DeploymentStatus.SUCCEEDED, DeploymentStatus.FAILED, DeploymentStatus.QUEUED):
        make_deployment(db, release, development, status)
    make_deployment(db, release, development, DeploymentStatus.AWAITING_APPROVAL)

    make_deployment(db, release, staging, DeploymentStatus.DEPLOYING)  # no error


def test_the_index_lists_exactly_the_active_statuses(db: Session) -> None:
    definition = db.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
        {"name": ONE_ACTIVE_PER_ENVIRONMENT},
    )
    assert definition is not None
    for status in DeploymentStatus:
        assert (f"'{status.value}'" in definition) == (status in ACTIVE_STATUSES)


def test_a_deployment_cannot_use_a_release_from_another_workspace(db: Session) -> None:
    own, other = make_workspace(db), make_workspace(db)
    foreign_release = make_release(db, make_application(db, other))
    environment = make_environment(db, make_application(db, own))

    db.add(
        Deployment(
            workspace_id=own.id,
            release_id=foreign_release.id,
            environment_id=environment.id,
            status=DeploymentStatus.QUEUED.value,
        )
    )
    with pytest.raises(IntegrityError, match="fk_deployments_release_id_releases"):
        db.flush()


def test_a_rollback_must_name_the_deployment_it_replaces(db: Session) -> None:
    application = make_application(db, make_workspace(db))
    release = make_release(db, application)
    environment = make_environment(db, application)

    db.add(
        Deployment(
            workspace_id=application.workspace_id,
            release_id=release.id,
            environment_id=environment.id,
            operation_type=OperationType.ROLLBACK.value,
            status=DeploymentStatus.QUEUED.value,
        )
    )
    with pytest.raises(IntegrityError, match="ck_deployments_rollback_of_deployment_id"):
        db.flush()


def test_an_unknown_status_is_refused(db: Session) -> None:
    application = make_application(db, make_workspace(db))
    deployment = make_deployment(
        db, make_release(db, application), make_environment(db, application)
    )

    with pytest.raises(IntegrityError, match="ck_deployments_status"):
        db.execute(
            text("UPDATE deployments SET status = 'pending' WHERE id = :id"), {"id": deployment.id}
        )


def _event(db: Session) -> DeploymentEvent:
    application = make_application(db, make_workspace(db))
    deployment = make_deployment(
        db, make_release(db, application), make_environment(db, application)
    )
    event = DeploymentEvent(
        workspace_id=deployment.workspace_id,
        deployment_id=deployment.id,
        to_status=DeploymentStatus.QUEUED.value,
        source=EventSource.POLICY.value,
    )
    db.add(event)
    db.flush()
    return event


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE deployment_events SET to_status = 'succeeded' WHERE id = :id",
        "DELETE FROM deployment_events WHERE id = :id",
    ],
)
def test_deployment_events_refuse_update_and_delete(db: Session, statement: str) -> None:
    event = _event(db)

    with pytest.raises(DBAPIError, match="deployment_events is append-only"):
        db.execute(text(statement), {"id": event.id})


def test_deployment_events_refuse_truncate(db: Session) -> None:
    _event(db)

    with pytest.raises(DBAPIError, match="deployment_events is append-only"):
        db.execute(text("TRUNCATE deployment_events"))


def test_a_version_is_registered_once_per_application(db: Session) -> None:
    application = make_application(db, make_workspace(db))
    make_release(db, application, version="1.4.0")

    with pytest.raises(IntegrityError, match="uq_releases_application_id_version"):
        make_release(db, application, version="1.4.0")


def test_the_same_version_in_another_application_is_fine(db: Session) -> None:
    workspace = make_workspace(db)
    make_release(db, make_application(db, workspace), version="1.4.0")
    make_release(db, make_application(db, workspace, name="Other"), version="1.4.0")


@pytest.mark.parametrize(
    "bad_digest",
    [
        "latest",
        "sha256:" + "A" * 64,  # uppercase hex
        "sha256:" + "a" * 63,
        "sha512:" + "a" * 64,
        "sha256:" + "g" * 64,  # not hex
    ],
)
def test_a_release_needs_an_image_digest(db: Session, bad_digest: str) -> None:
    with pytest.raises(IntegrityError, match="ck_releases_image_digest"):
        make_release(db, make_application(db, make_workspace(db)), image_digest=bad_digest)


def test_job_dedupe_keys_are_unique(db: Session) -> None:
    workspace = make_workspace(db)
    db.add(Job(workspace_id=workspace.id, kind="test.kind", dedupe_key="same"))
    db.flush()

    db.add(Job(workspace_id=workspace.id, kind="test.kind", dedupe_key="same"))
    with pytest.raises(IntegrityError, match="uq_jobs_dedupe_key"):
        db.flush()


def test_jobs_without_a_dedupe_key_never_collide(db: Session) -> None:
    workspace = make_workspace(db)
    db.add_all([Job(workspace_id=workspace.id, kind="test.kind") for _ in range(2)])
    db.flush()
