"""Tests for pre_bash.py (run: uv run --no-project --with pytest pytest .claude/hooks).

Regression for PR #21 (27 Nov 2026): an already-merged branch was pushed again and a new PR
opened from it. The merged-PR lookup is injected, so no network or gh is needed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "pre_bash", Path(__file__).with_name("pre_bash.py")
)
assert spec and spec.loader
pre_bash = importlib.util.module_from_spec(spec)
sys.modules["pre_bash"] = pre_bash
spec.loader.exec_module(pre_bash)

CURRENT = "feat/SCRUM-28-login-page"


@pytest.fixture(autouse=True)
def fake_current_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pre_bash, "current_branch", lambda cwd: CURRENT)


def merged(*branches: str):
    return lambda branch, cwd: 20 if branch in branches else None


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push -u origin feat/SCRUM-28-login-page",
        "git push --force-with-lease",
        "cd /d/PROJECTS/ReleaseGuard && git push origin HEAD",
        'gh pr create --title "x" --body "y"',
        "gh pr create --head feat/SCRUM-28-login-page --fill",
        "gh pr create --head=hamdounisabri1:feat/SCRUM-28-login-page",
        "git -C . push origin +feat/SCRUM-28-login-page:feat/SCRUM-28-login-page",
    ],
)
def test_blocks_push_or_pr_from_merged_branch(command: str) -> None:
    with pytest.raises(SystemExit) as exc:
        pre_bash.check_merged_branches(command, None, merged(CURRENT))
    assert exc.value.code == 2


@pytest.mark.parametrize(
    "command",
    [
        "git push origin --delete feat/SCRUM-28-login-page",
        "git push origin :feat/SCRUM-28-login-page",
        "git push --tags",
        "git push origin feat/SCRUM-30-31-applications-environments",
        "gh pr create --head feat/SCRUM-30-31-applications-environments",
        "git pull --rebase origin main",
        "gh pr list --head feat/SCRUM-28-login-page",
    ],
)
def test_allows_other_pushes(command: str) -> None:
    pre_bash.check_merged_branches(command, None, merged(CURRENT))


def test_allows_branch_without_merged_pr() -> None:
    pre_bash.check_merged_branches("git push && gh pr create --fill", None, merged())


def test_never_checks_main() -> None:
    assert pre_bash.branches_in_command("git push origin main", None) == []
