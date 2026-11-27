"""Tests for collect.py: plan parsing and schedule maths (no git or network needed)."""

import datetime as dt
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("collect", Path(__file__).with_name("collect.py"))
assert _spec and _spec.loader
collect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect)

PLAN = """\
# Plan

## 2. Scope
### In v1
- Approvals
- Rollback

## 3. Timeline
```mermaid
    M1 Sign in :milestone, m1, 2026-11-27 18:45, 0h
```
### Daily timetable
| Day | Sprint | Blocks | Planned | Buffer |
|---|---|---|---|---|
| Thu 26 Nov | S1 | x | 4 h | 1 h |
| Fri 27 Nov | S1 | x | 2 h + 15 min | 1 h |
| Sat 28 Nov | S2 | x | 3 h | 0 |
| **Total** | | | **9 h** | |

## 4. Sprint breakdown
### Sprint 1: Foundation (Thu 26 Nov) → `v0.1.0` · Epic SCRUM-12
- [x] SCRUM-1 *(2 h)* Models
- [x] SCRUM-2 *(30 min)* Seed
- [ ] SCRUM-3 *(1.5 h)* Login page
  - [ ] sub-item without a key is ignored
### Sprint 2: Releases (Sat 28 Nov) → `v0.2.0` · Epic SCRUM-13
- [ ] SCRUM-4 *(3 h)* Worker

## 5. Work tracking
### Today
- **Date:** Fri 27 Nov

## 6. Buffer, risks and cut list
### Top delivery risks
| Risk | Early signal | Response |
|---|---|---|
| Webhooks slow | Sat 17:15 | Use reconcile |
### Cut list (apply in this order if the schedule slips)
1. AI comparison
2. Grafana

**Never cut:** approvals, audit.

## 7. MVP acceptance checklist
- [x] **Setup:** done thing
- [ ] **Rollback:** open thing
"""


def test_sprints_count_tasks_and_hours_ignoring_keyless_subitems():
    s1, s2 = collect.parse_sprints(PLAN)
    assert (s1["number"], s1["epic"], s1["tag"], s1["title"]) == (1, "SCRUM-12", "v0.1.0", "Foundation")
    assert (s1["tasks_done"], s1["tasks_total"]) == (2, 3)
    assert (s1["hours_done"], s1["hours_total"]) == (2.5, 4.0)
    assert [t["key"] for t in s1["open_tasks"]] == ["SCRUM-3"]
    assert s1["closed"] is False and s2["hours_total"] == 3.0


def test_timetable_skips_total_row_and_reads_first_hour_figure():
    days = collect.parse_timetable(PLAN, 2026)
    assert [(d["date"], d["planned_hours"]) for d in days] == [
        ("2026-11-26", 4.0), ("2026-11-27", 2.0), ("2026-11-28", 3.0)]


def test_schedule_spi_buffer_and_rag_start_of_day():
    s = collect.schedule(PLAN, dt.date(2026, 11, 27))
    assert s["planned_value_start_of_day"] == 4.0  # only Thu is before today
    assert s["spi"] == 0.62  # 2.5 earned / 4 planned
    assert s["hours_remaining"] == 4.5
    assert s["working_days_left_incl_today"] == 2
    assert s["buffer_hours"] == 15.5
    assert s["rag"] == "red"  # SPI below 0.85, whatever the buffer
    assert s["current_sprint"] == 1


def test_schedule_before_the_first_day_has_no_spi():
    s = collect.schedule(PLAN, dt.date(2026, 11, 20))
    assert s["spi"] is None and s["rag"] == "n/a"


def test_plan_facts_milestones_risks_cut_list_and_mvp():
    f = collect.plan_facts(PLAN, dt.date(2026, 11, 27))
    assert f["milestones"] == [{"id": "M1", "name": "Sign in", "planned": "2026-11-27 18:45"}]
    assert f["risks"] == [{"risk": "Webhooks slow", "signal": "Sat 17:15", "response": "Use reconcile"}]
    assert f["cut_list"] == ["AI comparison", "Grafana"]
    assert f["never_cut"] == "approvals, audit."
    assert f["mvp_acceptance"] == [{"done": True, "item": "Setup: done thing"},
                                   {"done": False, "item": "Rollback: open thing"}]
    assert f["in_scope_v1"] == ["Approvals", "Rollback"]
    assert f["today_block"] == ["**Date:** Fri 27 Nov"]


def test_yaml_job_names():
    src = "on: push\njobs:\n  backend:\n    runs-on: x\n\n  frontend:\n    steps: []\n"
    assert collect.section_yaml_keys(src, "jobs") == ["backend", "frontend"]
