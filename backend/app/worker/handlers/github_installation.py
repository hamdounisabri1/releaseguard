"""``github.verify_installation``: confirm with GitHub that an installation linked by the install
callback really is an installation of our App, then mark the integration active or invalid.

GitHub is reached through an ``InstallationLookup``; the GitHub App client (SCRUM-44) provides
the real one (``GET /app/installations/{id}`` with the App JWT). Until it is wired into
``app/worker/registry.py`` this kind isn't registered, so its jobs wait in ``pending``.
"""

import asyncio
from typing import Protocol

from sqlalchemy.orm import Session

from app.schemas.jobs import VerifyInstallationPayload
from app.services import integration_service
from app.services.integration_service import InstallationInfo
from app.worker.runner import ClaimedJob, JobContext, JobSpec


class InstallationLookup(Protocol):
    async def get_installation(self, installation_id: int) -> InstallationInfo | None:
        """The installation's account and permissions, or ``None`` if GitHub answers 404 (not an
        installation of our App). Raises on transient errors, so the job is retried.
        """
        ...


def verify_installation_spec(lookup: InstallationLookup) -> JobSpec:
    async def handler(context: JobContext) -> None:
        job = context.job
        if job.workspace_id is None:
            raise ValueError("verify_installation job without a workspace")
        workspace_id = job.workspace_id
        payload = VerifyInstallationPayload.model_validate(job.payload)

        def read() -> int | None:
            with context.session() as db:
                return integration_service.pending_installation_id(
                    db, workspace_id, payload.integration_id
                )

        installation_id = await asyncio.to_thread(read)
        if installation_id is None:
            return  # disconnected meanwhile, or already verified
        # No transaction is open during the call.
        info = await lookup.get_installation(installation_id)

        def write() -> None:
            with context.session() as db:
                integration_service.complete_verification(
                    db, workspace_id, payload.integration_id, info
                )
                db.commit()

        await asyncio.to_thread(write)

    def on_dead(db: Session, job: ClaimedJob) -> None:
        # GitHub never answered: don't leave the link pending forever; the Admin can reconnect.
        if job.workspace_id is None:
            return
        payload = VerifyInstallationPayload.model_validate(job.payload)
        integration_service.complete_verification(
            db, job.workspace_id, payload.integration_id, None, reason="github_unreachable"
        )

    return JobSpec(handler, on_dead)
