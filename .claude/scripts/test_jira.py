"""Tests for jira.py (run: uv run --no-project --with pytest pytest .claude/hooks .claude/scripts).

No network: urllib.request.urlopen is replaced by a fake that records every call.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest

spec = importlib.util.spec_from_file_location("jira_cli", Path(__file__).with_name("jira.py"))
assert spec and spec.loader
jira = importlib.util.module_from_spec(spec)
sys.modules["jira_cli"] = jira
spec.loader.exec_module(jira)

SECRET = "tok-SHOULD-NEVER-PRINT"
ENV = {"JIRA_URL": "https://example.invalid", "JIRA_EMAIL": "me@x.invalid", "JIRA_API_TOKEN": SECRET}

TRANSITIONS = {
    "transitions": [
        {"id": "11", "name": "To Do"},
        {"id": "21", "name": "In Progress"},
        {"id": "31", "name": "Done"},
    ]
}


class FakeResp(io.BytesIO):
    def __enter__(self) -> FakeResp:
        return self

    def __exit__(self, *a: object) -> None:
        self.close()


class FakeJira:
    """Routes (method, path) to canned responses; fails for keys in `fail`."""

    def __init__(self, fail: set[str] | None = None, today: list[str] | None = None) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.fail = fail or set()
        self.today = today or []

    def __call__(self, req: Any, timeout: int = 0) -> FakeResp:
        method, path = req.get_method(), req.full_url.removeprefix(ENV["JIRA_URL"])
        body = json.loads(req.data) if req.data else None
        self.calls.append((method, path, body))
        if any(k in path for k in self.fail):
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, None)  # type: ignore[arg-type]
        if path.endswith("/transitions") and method == "GET":
            out: Any = TRANSITIONS
        elif path.startswith("/rest/api/3/search/jql"):
            out = {"issues": [{"key": k, "fields": {"labels": ["today"]}} for k in self.today]}
        else:
            out = None
        return FakeResp(json.dumps(out).encode() if out is not None else b"")


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeJira:
    f = FakeJira()
    monkeypatch.setattr(jira.urllib.request, "urlopen", f)
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    return f


def test_keys_arg_dedupes_and_rejects_foreign_keys() -> None:
    assert jira.keys_arg(["scrum-27,SCRUM-28", "SCRUM-27"]) == ["SCRUM-27", "SCRUM-28"]
    with pytest.raises(jira.JiraError):
        jira.keys_arg(["OTHER-1"])


def test_plan_tasks_reads_order_tick_and_estimate() -> None:
    text = "- [x] SCRUM-18 *(2 h)* a\n- [ ] SCRUM-27 *(1 h)* b\n- [ ] SCRUM-29 *(30 min)* c\n"
    assert jira.plan_tasks(text) == [
        ("SCRUM-18", True, "2 h"),
        ("SCRUM-27", False, "1 h"),
        ("SCRUM-29", False, "30 min"),
    ]


def test_adf_text_drops_stale_estimate_line() -> None:
    doc = jira.adf_doc("Goal line\nEstimate: 0.5d\nLast line")
    assert jira.adf_text(doc) == "Goal line\nLast line"


def test_start_looks_up_transition_once_and_comments(fake: FakeJira, capsys: Any) -> None:
    rc = jira.main(["start", "SCRUM-27", "SCRUM-28", "--comment", "plan"])
    assert rc == 0
    gets = [c for c in fake.calls if c[0] == "GET"]
    assert len(gets) == 1  # transition ids cached across keys
    posts = [c for c in fake.calls if c[1].endswith("/transitions") and c[0] == "POST"]
    assert [p[2]["transition"]["id"] for p in posts] == ["21", "21"]
    assert sum(1 for c in fake.calls if c[1].endswith("/comment")) == 2
    assert "SCRUM-28 -> In Progress ok" in capsys.readouterr().out


def test_done_partial_failure_exits_non_zero_and_continues(
    fake: FakeJira, capsys: Any
) -> None:
    fake.fail = {"SCRUM-27"}
    rc = jira.main(["done", "SCRUM-27", "SCRUM-28", "--pr", "https://example.invalid/pr/1"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "SCRUM-27 -> FAILED: POST /rest/api/3/issue/SCRUM-27/comment -> HTTP 400" in out
    assert "SCRUM-28 -> Done ok" in out
    label_ops = [c[2] for c in fake.calls if c[0] == "PUT" and "SCRUM-28" in c[1]]
    assert label_ops == [{"update": {"labels": [{"remove": "today"}]}}]


def test_dry_run_writes_nothing(fake: FakeJira) -> None:
    assert jira.main(["done", "--dry-run", "SCRUM-27"]) == 0
    assert jira.main(["start", "--dry-run", "SCRUM-27"]) == 0
    assert fake.calls == []


def test_today_sets_exact_set(fake: FakeJira) -> None:
    fake.today = ["SCRUM-26", "SCRUM-27"]
    assert jira.main(["today", "SCRUM-27", "SCRUM-28"]) == 0
    puts = {c[1].rsplit("/", 1)[1]: c[2]["update"]["labels"][0] for c in fake.calls if c[0] == "PUT"}
    assert puts == {"SCRUM-28": {"add": "today"}, "SCRUM-26": {"remove": "today"}}


def test_missing_env_is_an_error_not_a_crash(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    for k in ENV:
        monkeypatch.delenv(k, raising=False)
    assert jira.main(["brief", "SCRUM-27"]) == 1
    assert "missing env vars" in capsys.readouterr().err


def test_secrets_never_printed(fake: FakeJira, capsys: Any) -> None:
    fake.fail = {"SCRUM-27"}
    jira.main(["start", "SCRUM-27"])
    jira.main(["brief"])  # usage error path
    out = capsys.readouterr()
    for secret in (SECRET, ENV["JIRA_EMAIL"], ENV["JIRA_URL"]):
        assert secret not in out.out + out.err
