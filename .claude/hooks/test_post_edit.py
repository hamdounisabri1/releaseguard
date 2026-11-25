"""Regression tests for post_edit.py (run: uv run --no-project --with pytest pytest .claude/hooks).

Needs node and frontend/node_modules (pnpm install); skipped otherwise.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = Path(__file__).with_name("post_edit.py")
FRONTEND = ROOT / "frontend"

pytestmark = pytest.mark.skipif(
    not shutil.which("node") or not (FRONTEND / "node_modules" / "eslint").exists(),
    reason="needs node and frontend/node_modules",
)


def run_hook(file_path: Path) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_input": {"file_path": str(file_path)}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        check=False,
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def route_group_dir():
    # A route group path: parentheses broke the Windows eslint.cmd shim (SCRUM-26).
    # Unique name, created fresh, so the cleanup only ever removes what the test made.
    folder = FRONTEND / "app" / f"(hooktest-{uuid.uuid4().hex[:8]})"
    folder.mkdir()
    yield folder
    shutil.rmtree(folder)


def test_clean_file_in_route_group_passes(route_group_dir: Path) -> None:
    target = route_group_dir / "clean.ts"
    target.write_text("export const answer = 42;\n", encoding="utf-8")
    result = run_hook(target)
    assert result.returncode == 0, result.stderr


def test_lint_error_in_route_group_is_reported(route_group_dir: Path) -> None:
    target = route_group_dir / "bad.ts"
    target.write_text("const a: any = 1;\nexport default a;\n", encoding="utf-8")
    result = run_hook(target)
    assert result.returncode == 2
    assert "no-explicit-any" in result.stderr
