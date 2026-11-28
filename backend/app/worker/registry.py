"""The job kinds this worker runs, each with its handler and failure hook.

A kind that isn't registered is never claimed: its jobs wait in ``pending`` until a worker that
knows them runs (handy during a rolling upgrade, and while a handler's dependencies, such as the
GitHub client, aren't wired yet).
"""

from app.core.config import Settings
from app.worker.runner import JobSpec


def build_registry(settings: Settings) -> dict[str, JobSpec]:
    del settings  # the GitHub App client (SCRUM-44) is built from it
    return {}
