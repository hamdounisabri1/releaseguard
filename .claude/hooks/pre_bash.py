"""PreToolUse hook for Bash and PowerShell commands.

1. Blocks commands that read secret files (.env, *.pem, *.key). .env.example is allowed.
2. On `git commit`, runs gitleaks on the staged changes if a gitleaks binary is on PATH.
   Otherwise it does nothing here; the pre-commit gitleaks hook (.pre-commit-config.yaml)
   still scans every commit.

Exit code 2 blocks the tool call and shows stderr to Claude.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

READ_VERBS = (
    r"cat|type|get-content|gc|less|more|head|tail|bat|nl|strings|xxd|od|"
    r"select-string|sls|grep|rg|findstr|awk|sed|source|base64|curl|scp"
)
SECRET_FILE = r"""(?:^|[\s/\\"'=:])(?:\.env(?:\.(?!example\b)[\w.-]+)?|[\w.-]+\.(?:pem|key))(?=$|[\s"'|;&>)])"""
SECRET_READ = re.compile(rf"(?i)(?:^|[\s;&|(])(?:{READ_VERBS})\b[^;&|]*{SECRET_FILE}")
GIT_COMMIT = re.compile(r"(?i)\bgit\b(?:\s+-[^\s]+(?:\s+[^\s-][^\s]*)?)*\s+commit\b")
LEAK_EXIT = 99


def block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def run_gitleaks() -> None:
    if not shutil.which("gitleaks"):
        return
    attempts = (
        ["gitleaks", "git", "--staged", "--redact", "--no-banner", "--exit-code", str(LEAK_EXIT)],
        ["gitleaks", "protect", "--staged", "--redact", "--no-banner", "--exit-code", str(LEAK_EXIT)],
    )
    for args in attempts:
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
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


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return

    if SECRET_READ.search(command):
        block(
            "Blocked: this command reads a secret file (.env, *.pem or *.key). "
            "Secrets must not enter the transcript. Use .env.example for variable names."
        )

    if GIT_COMMIT.search(command):
        run_gitleaks()


if __name__ == "__main__":
    main()
