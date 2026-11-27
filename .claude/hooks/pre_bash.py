"""PreToolUse hook for Bash and PowerShell commands.

1. Blocks commands that read secret files (.env, *.pem, *.key). .env.example is allowed.
2. On `git commit`, runs gitleaks on the staged changes if a gitleaks binary is on PATH.
   Otherwise it does nothing here; the pre-commit gitleaks hook (.pre-commit-config.yaml)
   still scans every commit.
3. On `git push` and `gh pr create`, blocks when the branch already has a merged PR.
   Rebase-merge gives the commits new SHAs on main, so pushing the old branch again
   restores it on GitHub and a new PR shows already-merged work as new, with conflicts
   (PR #21, 27 Nov 2026). Fails open when gh is missing or offline.

Exit code 2 blocks the tool call and shows stderr to Claude.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable

READ_VERBS = (
    r"cat|type|get-content|gc|less|more|head|tail|bat|nl|strings|xxd|od|"
    r"select-string|sls|grep|rg|findstr|awk|sed|source|base64|curl|scp"
)
SECRET_FILE = r"""(?:^|[\s/\\"'=:])(?:\.env(?:\.(?!example\b)[\w.-]+)?|[\w.-]+\.(?:pem|key))(?=$|[\s"'|;&>)])"""
SECRET_READ = re.compile(rf"(?i)(?:^|[\s;&|(])(?:{READ_VERBS})\b[^;&|]*{SECRET_FILE}")
GIT_COMMIT = re.compile(r"(?i)\bgit\b(?:\s+-[^\s]+(?:\s+[^\s-][^\s]*)?)*\s+commit\b")
GIT_PUSH = re.compile(
    r"(?i)\bgit\b(?:\s+-[^\s]+(?:\s+[^\s-][^\s]*)?)*\s+push\b([^;&|]*)"
)
GH_PR_CREATE = re.compile(r"(?i)\bgh\s+pr\s+create\b([^;&|]*)")
PROTECTED_BRANCHES = {"main", "master", "HEAD"}
LEAK_EXIT = 99

MergedLookup = Callable[[str, str | None], int | None]


def block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def run_gitleaks() -> None:
    if not shutil.which("gitleaks"):
        return
    attempts = (
        [
            "gitleaks",
            "git",
            "--staged",
            "--redact",
            "--no-banner",
            "--exit-code",
            str(LEAK_EXIT),
        ],
        [
            "gitleaks",
            "protect",
            "--staged",
            "--redact",
            "--no-banner",
            "--exit-code",
            str(LEAK_EXIT),
        ],
    )
    for args in attempts:
        try:
            result = subprocess.run(
                args, check=False, capture_output=True, text=True, timeout=60
            )
        except (OSError, subprocess.TimeoutExpired):
            return
        if result.returncode == 0:
            return
        if result.returncode == LEAK_EXIT:
            block(
                "gitleaks found possible secrets in the staged changes. Commit blocked.\n"
                + (result.stdout or result.stderr)[-2000:]
            )
        # Any other code: probably an unknown subcommand on this gitleaks version; try the next form.
    print("pre_bash hook: gitleaks could not run; commit not scanned.", file=sys.stderr)


def _split(args: str) -> list[str]:
    try:
        return shlex.split(args, posix=True)
    except ValueError:
        return args.split()


def current_branch(cwd: str | None) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    branch = result.stdout.strip()
    return branch if result.returncode == 0 and branch else None


def branches_in_command(command: str, cwd: str | None) -> list[str]:
    """Branches a `git push` or `gh pr create` in this command would publish."""
    branches: list[str] = []
    for match in GIT_PUSH.finditer(command):
        args = _split(match.group(1))
        if any(a in ("-d", "--delete", "--tags") or a.startswith(":") for a in args):
            continue  # deleting a remote branch or pushing tags is fine
        positional = [a for a in args if not a.startswith("-")]
        if len(positional) >= 2:
            for refspec in positional[1:]:
                src = refspec.lstrip("+").split(":", 1)[0]
                branches.append(src or "HEAD")
        else:
            branches.append("HEAD")
    for match in GH_PR_CREATE.finditer(command):
        args = _split(match.group(1))
        head = None
        for i, arg in enumerate(args):
            if arg in ("-H", "--head") and i + 1 < len(args):
                head = args[i + 1]
            elif arg.startswith("--head="):
                head = arg.split("=", 1)[1]
        branches.append(head.split(":")[-1] if head else "HEAD")
    resolved: list[str] = []
    for branch in branches:
        name = current_branch(cwd) if branch == "HEAD" else branch
        if name and name not in PROTECTED_BRANCHES and name not in resolved:
            resolved.append(name)
    return resolved


def merged_pr(branch: str, cwd: str | None) -> int | None:
    """Number of a merged PR whose head is `branch`, or None (also when gh can't answer)."""
    if not shutil.which("gh"):
        return None
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "merged",
                "--limit",
                "1",
                "--json",
                "number",
                "--jq",
                ".[0].number // empty",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = result.stdout.strip()
    return int(out) if result.returncode == 0 and out.isdigit() else None


def check_merged_branches(
    command: str, cwd: str | None, lookup: MergedLookup = merged_pr
) -> None:
    for branch in branches_in_command(command, cwd):
        number = lookup(branch, cwd)
        if number is not None:
            block(
                f"Blocked: branch '{branch}' was already merged in PR #{number}. Rebase-merge "
                "put its commits on main with new SHAs, so pushing it again restores a stale "
                "branch and a new PR shows merged work as new (with conflicts). Delete the "
                f"local branch (git branch -D {branch}), pull main, and put any new work on "
                "a new branch."
            )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return
    cwd = payload.get("cwd") or None

    if SECRET_READ.search(command):
        block(
            "Blocked: this command reads a secret file (.env, *.pem or *.key). "
            "Secrets must not enter the transcript. Use .env.example for variable names."
        )

    if GIT_COMMIT.search(command):
        run_gitleaks()

    if GIT_PUSH.search(command) or GH_PR_CREATE.search(command):
        check_merged_branches(command, cwd)


if __name__ == "__main__":
    main()
