"""Workspace scoping by construction: every public function in a tenant repository takes
``workspace_id`` right after the session, so no unscoped tenant query can exist.
"""

import importlib
import inspect
import pkgutil

import app.repositories

# Lookups that run before the caller's workspace is known (login, session cookie). Nothing else
# belongs on this list.
UNSCOPED_REPOSITORIES = {"app.repositories.identity"}


def _tenant_repositories() -> list[str]:
    names = [
        f"{app.repositories.__name__}.{module.name}"
        for module in pkgutil.iter_modules(app.repositories.__path__)
    ]
    return [name for name in names if name not in UNSCOPED_REPOSITORIES]


def test_there_are_tenant_repositories_to_check() -> None:
    assert "app.repositories.audit" in _tenant_repositories()


def test_every_tenant_repository_function_takes_workspace_id() -> None:
    offenders = []
    for module_name in _tenant_repositories():
        module = importlib.import_module(module_name)
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("_") or function.__module__ != module_name:
                continue
            parameters = list(inspect.signature(function).parameters)
            if parameters[:2] != ["db", "workspace_id"]:
                offenders.append(f"{module_name}.{name}{tuple(parameters)}")

    assert offenders == []
