"""PostToolUse hook for Edit / Write / MultiEdit.

- backend/**/*.py  -> ruff format + ruff check --fix (via uv), once backend/pyproject.toml exists.
- frontend/**/*.{ts,tsx,js,jsx} -> eslint --fix, once frontend/node_modules is installed.

Does nothing when the tooling isn't set up yet (pre-code safe).
Exit code 2 shows remaining lint errors to Claude so it can fix them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 60


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args, check=False, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def report(
    result: subprocess.CompletedProcess[str] | None,
    label: str,
    *,
    quiet_if_missing: bool = False,
) -> None:
    if result is None or result.returncode == 0:
        return
    output = (result.stdout + result.stderr).strip()
    # `uv run ruff` before ruff is installed: stay silent. Only for callers that can't check
    # the tool exists up front; otherwise a real finding mentioning "not found" is dropped.
    missing = ("failed to spawn", "not found", "no such file", "cannot find")
    if quiet_if_missing and any(s in output.lower() for s in missing):
        return
    print(f"{label} reported problems:\n{output[-3000:]}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return

    root = Path(
        os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    ).resolve()
    path = Path(file_path)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        rel = path.relative_to(root)
    except ValueError:
        return
    if not path.exists() or not rel.parts:
        return

    backend, frontend = root / "backend", root / "frontend"

    if rel.parts[0] == "backend" and path.suffix == ".py":
        if not (backend / "pyproject.toml").exists() or not shutil.which("uv"):
            return
        target = str(path.relative_to(backend))
        run(["uv", "run", "--quiet", "ruff", "format", target], backend)
        report(
            run(["uv", "run", "--quiet", "ruff", "check", "--fix", target], backend),
            "ruff",
            quiet_if_missing=True,
        )

    elif rel.parts[0] == "frontend" and path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
        # Run eslint's JS entry with node directly. The Windows `.bin/eslint.cmd` shim goes
        # through cmd.exe, which breaks on paths with parentheses (route groups: app/(app)/…).
        eslint = frontend / "node_modules" / "eslint" / "bin" / "eslint.js"
        node = shutil.which("node")
        if not eslint.exists() or not node:
            return
        target = str(path.relative_to(frontend))
        report(run([node, str(eslint), "--fix", target], frontend), "eslint")


if __name__ == "__main__":
    main()
