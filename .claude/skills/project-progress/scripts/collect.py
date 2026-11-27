"""Collect the facts for a full ReleaseGuard progress report as JSON.

Stdlib only, read-only. Run from anywhere inside the repo:

    py -3 .claude/skills/project-progress/scripts/collect.py [--today YYYY-MM-DD] [--no-network]

It reads tracked files only (``git ls-files``), never ``.env`` or key files,
and prints variable *names* from ``.env.example``, never values. ``gh`` is used
for open/merged PR counts and the latest CI run unless ``--no-network``.
Jira status comes from ``.claude/scripts/jira.py`` (run separately by the skill).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HOURS_PER_DAY = 10.0
_EST = re.compile(r"\*\((\d+(?:\.\d+)?) ?(h|min)\)\*")
_TASK = re.compile(r"^- \[( |x)\] (SCRUM-\d+) (.*)$")
_SPRINT = re.compile(r"^### Sprint (\d+): (.+)$")
_DAY_ROW = re.compile(r"^\| (?:\*\*)?(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\d{1,2}) ([A-Z][a-z]{2})")
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


# ---------------------------------------------------------------- helpers
def run(cmd: list[str], cwd: Path, timeout: int = 20) -> str | None:
    try:
        out = subprocess.run(cmd, check=False, cwd=cwd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def section(text: str, heading: str) -> str:
    """Body of a markdown section (from its heading to the next heading of the same level)."""
    m = re.search(rf"^(#+) {re.escape(heading)}.*$", text, re.MULTILINE)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(rf"^#{{1,{level}}} ", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def hours(text: str) -> float:
    m = _EST.search(text)
    if not m:
        return 0.0
    v = float(m.group(1))
    return v / 60 if m.group(2) == "min" else v


# ---------------------------------------------------------------- schedule
def parse_sprints(plan: str) -> list[dict[str, Any]]:
    body = section(plan, "4. Sprint breakdown")
    sprints: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for line in body.splitlines():
        m = _SPRINT.match(line)
        if m:
            title = m.group(2)
            cur = {
                "number": int(m.group(1)),
                "title": title.split(" (")[0].strip(),
                "heading": title,
                "epic": (re.search(r"Epic (SCRUM-\d+)", title) or [None, None])[1],
                "tag": (re.search(r"`(v\d+\.\d+\.\d+)`", title) or [None, None])[1],
                "tasks": [],
            }
            sprints.append(cur)
            continue
        m = _TASK.match(line)
        if m and cur is not None:
            text = _EST.sub("", m.group(3)).strip()
            cur["tasks"].append({
                "key": m.group(2),
                "done": m.group(1) == "x",
                "hours": round(hours(m.group(3)), 2),
                "title": re.sub(r"\s+", " ", text)[:140],
            })
    for s in sprints:
        t = s["tasks"]
        s["tasks_total"] = len(t)
        s["tasks_done"] = sum(x["done"] for x in t)
        s["hours_total"] = round(sum(x["hours"] for x in t), 2)
        s["hours_done"] = round(sum(x["hours"] for x in t if x["done"]), 2)
        s["closed"] = bool(t) and s["tasks_done"] == s["tasks_total"]
        s["open_tasks"] = [x for x in t if not x["done"]]
        del s["tasks"]
    return sprints


def parse_timetable(plan: str, year: int) -> list[dict[str, Any]]:
    """Rows of the 'Daily timetable' table: date and planned hours."""
    days = []
    for line in section(plan, "Daily timetable").splitlines():
        m = _DAY_ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        planned = re.match(r"\**(\d+(?:\.\d+)?) h", cells[3]) if len(cells) > 3 else None
        days.append({
            "date": dt.date(year, _MONTHS[m.group(3)], int(m.group(2))).isoformat(),
            "sprint": cells[1],
            "planned_hours": float(planned.group(1)) if planned else 0.0,
        })
    return days


def schedule(plan: str, today: dt.date) -> dict[str, Any]:
    sprints = parse_sprints(plan)
    days = parse_timetable(plan, today.year)
    total = round(sum(s["hours_total"] for s in sprints), 2)
    done = round(sum(s["hours_done"] for s in sprints), 2)
    # Planned value: everything scheduled on days *before* today (start-of-day view).
    pv = round(sum(d["planned_hours"] for d in days if d["date"] < today.isoformat()), 2)
    pv_eod = round(sum(d["planned_hours"] for d in days if d["date"] <= today.isoformat()), 2)
    days_left = sum(1 for d in days if d["date"] >= today.isoformat())
    remaining = round(total - done, 2)
    capacity = days_left * HOURS_PER_DAY
    spi = round(done / pv, 2) if pv else None
    if spi is None or not days:
        rag = "n/a"
    elif spi >= 0.95 and capacity >= remaining:
        rag = "green"
    elif spi >= 0.85 and capacity >= remaining * 0.95:
        rag = "amber"
    else:
        rag = "red"
    current = next((s for s in sprints if not s["closed"]), None)
    return {
        "today": today.isoformat(),
        "hours_total": total,
        "hours_done": done,
        "percent_done": round(100 * done / total, 1) if total else 0.0,
        "tasks_total": sum(s["tasks_total"] for s in sprints),
        "tasks_done": sum(s["tasks_done"] for s in sprints),
        "planned_value_start_of_day": pv,
        "planned_value_end_of_day": pv_eod,
        "spi": spi,
        "hours_remaining": remaining,
        "working_days_left_incl_today": days_left,
        "capacity_hours_left": capacity,
        "buffer_hours": round(capacity - remaining, 2),
        "required_hours_per_day": round(remaining / days_left, 2) if days_left else None,
        "rag": rag,
        "current_sprint": current["number"] if current else None,
        "sprints": sprints,
        "timetable": days,
    }


def milestones(plan: str) -> list[dict[str, str]]:
    out = []
    for m in re.finditer(r"^\s*(M\d) (.+?)\s*:milestone, \w+, (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", plan, re.MULTILINE):
        out.append({"id": m.group(1), "name": m.group(2).strip(), "planned": m.group(3)})
    return out


def checklist(text: str) -> list[dict[str, Any]]:
    return [{"done": m.group(1) == "x", "item": re.sub(r"\*\*", "", m.group(2)).strip()}
            for m in re.finditer(r"^- \[( |x)\] (.+)$", text, re.MULTILINE)]


def numbered(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^\d+\. (.+)$", text, re.MULTILINE)]


def table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows[1:]  # drop header


def plan_facts(plan: str, today: dt.date) -> dict[str, Any]:
    risks = section(plan, "Top delivery risks")
    cut = section(plan, "Cut list")
    never = re.search(r"\*\*Never cut:\*\* (.+)", plan)
    today_block = section(plan, "Today")
    return {
        "schedule": schedule(plan, today),
        "milestones": milestones(plan),
        "mvp_acceptance": checklist(section(plan, "7. MVP acceptance checklist")),
        "risks": [{"risk": r[0], "signal": r[1], "response": r[2]}
                  for r in table_rows(risks) if len(r) >= 3],
        "cut_list": numbered(cut),
        "never_cut": never.group(1) if never else "",
        "in_scope_v1": [ln[2:].strip() for ln in section(plan, "In v1").splitlines()
                        if ln.startswith("- ")],
        "today_block": [ln[2:].strip() for ln in today_block.splitlines() if ln.startswith("- ")],
    }


# ---------------------------------------------------------------- codebase
def tracked(root: Path) -> list[str]:
    out = run(["git", "ls-files"], root)
    return out.splitlines() if out else []


def structure(root: Path, files: list[str]) -> list[dict[str, Any]]:
    areas = ["backend/app", "backend/tests", "backend/migrations", "frontend/app",
             "frontend/components", "frontend/services", "frontend/lib", "frontend/hooks",
             "frontend/types", "worker", "infra", "docs", ".github", ".claude"]
    code_ext = {".py", ".ts", ".tsx", ".js", ".mjs", ".css", ".yml", ".yaml", ".sh", ".md", ".json"}
    out = []
    for a in areas:
        fs = [f for f in files if f == a or f.startswith(a + "/")]
        if a == ".claude":
            fs = [f for f in fs if not f.startswith(".claude/skills/")]
        lines = 0
        for f in fs:
            if Path(f).suffix in code_ext:
                try:
                    lines += sum(1 for _ in (root / f).open(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
        placeholder = bool(fs) and all(Path(f).name == "README.md" for f in fs)
        out.append({"path": a, "files": len(fs), "lines": lines,
                    "state": "missing" if not fs else "placeholder" if placeholder else "active"})
    return out


def backend_facts(root: Path, files: list[str]) -> dict[str, Any]:
    routes = []
    for f in sorted(x for x in files if x.startswith("backend/app/api/") and x.endswith(".py")):
        src = read(root, f)
        pm = re.search(r"APIRouter\((?:[^()]|\([^()]*\))*?prefix=\"([^\"]*)\"", src, re.DOTALL)
        prefix = pm.group(1) if pm else ""
        for m in re.finditer(r"@router\.(get|post|put|patch|delete)\(\s*\"([^\"]*)\"(.*?)\)\n"
                             r"(?:async )?def", src, re.DOTALL):
            summ = re.search(r"summary=\"([^\"]+)\"", m.group(3))
            routes.append({"method": m.group(1).upper(),
                           "path": "/api/v1" + prefix + m.group(2) if "v1" in f else prefix + m.group(2),
                           "summary": summ.group(1) if summ else ""})
        for m in re.finditer(r"@app\.(get|post)\(\s*\"([^\"]+)\"", src):
            routes.append({"method": m.group(1).upper(), "path": m.group(2), "summary": ""})
    main = read(root, "backend/app/main.py") + "".join(
        read(root, f) for f in files if f.startswith("backend/app/api/") and "health" in f)
    for m in re.finditer(r"@\w+\.(get|post)\(\s*\"(/(?:healthz|readyz)[^\"]*)\"", main):
        if not any(r["path"] == m.group(2) for r in routes):
            routes.append({"method": m.group(1).upper(), "path": m.group(2), "summary": ""})
    tables = []
    for f in files:
        if f.startswith("backend/app/models/") and f.endswith(".py"):
            tables += re.findall(r"__tablename__ = \"(\w+)\"", read(root, f))
    tests = [f for f in files if re.match(r"backend/tests/.*test_.*\.py$", f)]
    n_tests = sum(len(re.findall(r"^\s*(?:async )?def test_", read(root, f), re.MULTILINE)) for f in tests)
    deps = re.search(r"^dependencies = \[(.*?)\]", read(root, "backend/pyproject.toml"), re.DOTALL | re.MULTILINE)
    return {
        "python": read(root, "backend/.python-version").strip(),
        "dependencies": re.findall(r"\"([^\"]+)\"", deps.group(1)) if deps else [],
        "routes": routes,
        "tables": sorted(set(tables)),
        "migrations": [Path(f).name for f in files
                       if f.startswith("backend/migrations/versions/") and f.endswith(".py")],
        "services": sorted(Path(f).stem for f in files
                           if f.startswith("backend/app/services/") and f.endswith(".py")
                           and not f.endswith("__init__.py")),
        "test_files": len(tests),
        "test_functions": n_tests,
    }


def frontend_facts(root: Path, files: list[str]) -> dict[str, Any]:
    pkg_txt = read(root, "frontend/package.json")
    pkg = json.loads(pkg_txt) if pkg_txt else {}
    pages = []
    for f in files:
        if f.startswith("frontend/app/") and f.endswith("/page.tsx"):
            route = "/" + "/".join(p for p in f[len("frontend/app/"):-len("/page.tsx")].split("/")
                                   if not p.startswith("("))
            pages.append(route)
    comps = [f for f in files if f.startswith("frontend/components/") and f.endswith(".tsx")
             and ".test." not in f]
    return {
        "package_manager": pkg.get("packageManager"),
        "dependencies": pkg.get("dependencies", {}),
        "dev_dependencies": sorted(pkg.get("devDependencies", {})),
        "scripts": sorted(pkg.get("scripts", {})),
        "pages": sorted(pages),
        "components": {
            "ui_primitives": sum(f.startswith("frontend/components/ui/") for f in comps),
            "app_components": sum(not f.startswith("frontend/components/ui/") for f in comps),
        },
        "test_files": sum(bool(re.search(r"\.test\.tsx?$", f)) for f in files
                          if f.startswith("frontend/")),
    }


def environment_facts(root: Path, files: list[str]) -> dict[str, Any]:
    names = re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", read(root, ".env.example"), re.MULTILINE)
    compose = [f for f in files if re.search(r"(^|/)(docker-)?compose[^/]*\.ya?ml$", f)]
    dockerfiles = [f for f in files if Path(f).name.startswith("Dockerfile")]
    workflows = {}
    for f in files:
        if f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml")):
            src = read(root, f)
            jobs = section_yaml_keys(src, "jobs")
            workflows[Path(f).name] = jobs
    return {
        "env_example_variables": list(dict.fromkeys(names)),
        "compose_files": compose,
        "dockerfiles": dockerfiles,
        "ci_workflows": workflows,
        "precommit_hooks": re.findall(r"^\s*- id: ([\w-]+)", read(root, ".pre-commit-config.yaml"), re.MULTILINE),
    }


def section_yaml_keys(src: str, key: str) -> list[str]:
    m = re.search(rf"^{key}:\n((?:[ \t].*\n|\n)*)", src, re.MULTILINE)
    return re.findall(r"^  ([\w-]+):", m.group(1), re.MULTILINE) if m else []


def docs_facts(root: Path, files: list[str]) -> dict[str, Any]:
    adrs = []
    for f in sorted(x for x in files if re.match(r"docs/adr/\d{4}-", x)):
        title = re.search(r"^# (.+)$", read(root, f), re.MULTILINE)
        adrs.append(title.group(1) if title else Path(f).stem)
    return {
        "adrs": adrs,
        "retros": [f for f in files if f.startswith("docs/retros/")],
        "docs": [f for f in files if f.startswith("docs/") and f.endswith(".md")
                 and "/adr/" not in f and "/retros/" not in f],
        "rules": sorted(Path(f).stem for f in files if f.startswith(".claude/rules/")),
        "skills": sorted({f.split("/")[2] for f in files if f.startswith(".claude/skills/")}),
        "commands": sorted(Path(f).stem for f in files if f.startswith(".claude/commands/")),
        "agents": sorted(Path(f).stem for f in files if f.startswith(".claude/agents/")),
    }


def git_facts(root: Path, network: bool) -> dict[str, Any]:
    log = run(["git", "log", "--format=%h|%ad|%s", "--date=short", "origin/main", "-n", "15"], root) \
        or run(["git", "log", "--format=%h|%ad|%s", "--date=short", "-n", "15"], root) or ""
    count = (run(["git", "rev-list", "--count", "origin/main"], root) or "").strip()
    by_day = run(["git", "log", "origin/main", "--format=%ad", "--date=short"], root) or ""
    per_day: dict[str, int] = {}
    for d in by_day.split():
        per_day[d] = per_day.get(d, 0) + 1
    facts: dict[str, Any] = {
        "branch": (run(["git", "branch", "--show-current"], root) or "").strip(),
        "commits_on_main": int(count) if count.isdigit() else None,
        "commits_per_day": dict(sorted(per_day.items())),
        "tags": (run(["git", "tag", "--sort=-creatordate"], root) or "").split(),
        "recent_commits": [dict(zip(("sha", "date", "subject"), ln.split("|", 2)))
                           for ln in log.splitlines() if ln],
    }
    if network:
        prs = run(["gh", "pr", "list", "--state", "all", "--limit", "200",
                   "--json", "number,title,state,isDraft"], root)
        if prs:
            items = json.loads(prs)
            facts["pull_requests"] = {
                "merged": sum(p["state"] == "MERGED" for p in items),
                "open": [f"#{p['number']} {p['title']}" + (" (draft)" if p["isDraft"] else "")
                         for p in items if p["state"] == "OPEN"],
            }
        ci = run(["gh", "run", "list", "--branch", "main", "--limit", "1",
                  "--json", "status,conclusion,displayTitle,createdAt,url"], root)
        if ci:
            runs = json.loads(ci)
            facts["latest_main_ci"] = runs[0] if runs else None
    return facts


def collect(root: Path, today: dt.date, network: bool) -> dict[str, Any]:
    files = tracked(root)
    claude = read(root, "CLAUDE.md")
    cur = re.search(r"\*\*Current sprint:([^*]+)", claude)
    return {
        "generated_for": today.isoformat(),
        "current_sprint_line": cur.group(1).strip() if cur else "",
        "plan": plan_facts(read(root, "docs/PROJECT_PLAN.md"), today),
        "structure": structure(root, files),
        "backend": backend_facts(root, files),
        "frontend": frontend_facts(root, files),
        "environments": environment_facts(root, files),
        "docs_and_tooling": docs_facts(root, files),
        "git": git_facts(root, network),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--no-network", action="store_true", help="skip gh (PRs, CI runs)")
    ap.add_argument("--root", type=Path, default=None)
    a = ap.parse_args(argv)
    root = a.root or Path(run(["git", "rev-parse", "--show-toplevel"], Path.cwd()) or ".").resolve()
    root = Path(str(root).strip())
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(json.dumps(collect(root, a.today, not a.no_network), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
